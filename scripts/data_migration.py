#!/usr/bin/env python3
"""
Data Migration Utilities - Safe migration between data storage formats.

This script provides utilities to migrate data between different storage formats,
backup data before migration, and rollback if issues occur.
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import redis
import argparse
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DataMigrationManager:
    """Manages safe data migration between storage formats."""

    def __init__(self, redis_client: redis.Redis, backup_dir: str = "./backups"):
        self.redis = redis_client
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

        # Migration tracking
        self.migration_log_key = "migration:log"
        self.migration_backup_key = "migration:backups"

    def create_backup(self, instruments: List[str] = None,
                     data_types: List[str] = None) -> str:
        """Create a comprehensive backup of current data.

        Args:
            instruments: List of instruments to backup (None for all)
            data_types: List of data types to backup ['ohlc', 'indicators', 'ticks']

        Returns:
            Backup ID for restoration
        """
        backup_id = f"backup_{int(time.time())}"
        backup_path = self.backup_dir / f"{backup_id}.json"

        logger.info(f"Creating backup: {backup_id}")

        backup_data = {
            'backup_id': backup_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'instruments': instruments or ['*'],
            'data_types': data_types or ['ohlc', 'indicators', 'ticks'],
            'data': {}
        }

        try:
            # Backup OHLC data
            if 'ohlc' in backup_data['data_types']:
                backup_data['data']['ohlc'] = self._backup_ohlc_data(instruments)

            # Backup indicators
            if 'indicators' in backup_data['data_types']:
                backup_data['data']['indicators'] = self._backup_indicators(instruments)

            # Backup ticks
            if 'ticks' in backup_data['data_types']:
                backup_data['data']['ticks'] = self._backup_ticks(instruments)

            # Save backup to file
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)

            # Record backup in Redis
            self.redis.hset(self.migration_backup_key, backup_id, json.dumps({
                'path': str(backup_path),
                'timestamp': backup_data['timestamp'],
                'size': len(backup_data['data'])
            }))

            logger.info(f"Backup created successfully: {backup_id} ({len(backup_data['data'])} data types)")
            return backup_id

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            # Clean up partial backup
            if backup_path.exists():
                backup_path.unlink()
            raise

    def _backup_ohlc_data(self, instruments: List[str] = None) -> Dict[str, Any]:
        """Backup OHLC data."""
        data = {}

        # Get all OHLC keys
        ohlc_keys = self.redis.keys('ohlc:*')
        logger.info(f"Found {len(ohlc_keys)} OHLC keys to backup")

        for key in ohlc_keys:
            try:
                # Parse key to get instrument and timeframe
                parts = key.split(':')
                if len(parts) >= 3:
                    instrument = parts[1]
                    timeframe = parts[2]

                    # Filter by instruments if specified
                    if instruments and instrument not in instruments and '*' not in instruments:
                        continue

                    # Get data
                    value = self.redis.get(key)
                    if value:
                        if instrument not in data:
                            data[instrument] = {}
                        if timeframe not in data[instrument]:
                            data[instrument][timeframe] = {}

                        # For individual keys, store as is
                        if len(parts) > 3:  # Individual key format
                            timestamp_part = ':'.join(parts[3:])
                            data[instrument][timeframe][timestamp_part] = value
                        else:  # Sorted set format
                            data[instrument][timeframe]['sorted_set'] = value

            except Exception as e:
                logger.warning(f"Failed to backup OHLC key {key}: {e}")

        return data

    def _backup_indicators(self, instruments: List[str] = None) -> Dict[str, Any]:
        """Backup technical indicators."""
        data = {}

        indicator_keys = self.redis.keys('indicators:*')
        logger.info(f"Found {len(indicator_keys)} indicator keys to backup")

        for key in indicator_keys:
            try:
                parts = key.split(':')
                if len(parts) >= 3:
                    instrument = parts[1]
                    indicator_name = ':'.join(parts[2:])

                    # Filter by instruments if specified
                    if instruments and instrument not in instruments and '*' not in instruments:
                        continue

                    value = self.redis.get(key)
                    if value:
                        if instrument not in data:
                            data[instrument] = {}
                        data[instrument][indicator_name] = value

            except Exception as e:
                logger.warning(f"Failed to backup indicator {key}: {e}")

        return data

    def delete_legacy_keys(self, instruments: List[str] = None, dry_run: bool = True) -> Dict[str, Any]:
        """Delete legacy individual OHLC keys that are already present in the sorted set.

        This method will:
         - Identify candidate individual keys where a matching bar exists in the sorted set
         - Backup those keys to a file before deletion
         - Delete keys if dry_run is False and --confirm was given

        Returns a report with details: candidate_keys, deleted_keys, backup_path, by_instrument
        """
        report = {
            'candidate_keys': 0,
            'deleted_keys': 0,
            'backup_path': None,
            'by_instrument': {}
        }

        try:
            # Find all instruments/timeframes to consider
            pattern = 'ohlc:*' if not instruments else f'ohlc:{instruments[0]}:*'
            all_keys = self.redis.keys(pattern)

            # Group by instrument/timeframe
            instrument_timeframes = {}
            for key in all_keys:
                parts = key.split(':')
                if len(parts) >= 4:
                    instrument = parts[1]
                    timeframe = parts[2]

                    if instruments and instrument not in instruments:
                        continue

                    if instrument not in instrument_timeframes:
                        instrument_timeframes[instrument] = {}
                    if timeframe not in instrument_timeframes[instrument]:
                        instrument_timeframes[instrument][timeframe] = []

                    instrument_timeframes[instrument][timeframe].append(key)

            candidates = []
            by_instrument = {}

            # Identify candidates
            for instrument, timeframes in instrument_timeframes.items():
                by_instrument.setdefault(instrument, 0)
                for timeframe, keys in timeframes.items():
                    sorted_key = f'ohlc_sorted:{instrument}:{timeframe}'
                    sorted_entries = self.redis.zrange(sorted_key, 0, -1)

                    # Build quick lookup of timestamps present in sorted set
                    timestamps_in_sorted = set()
                    for je in sorted_entries:
                        try:
                            entry = json.loads(je)
                            timestamps_in_sorted.add(entry.get('timestamp'))
                        except Exception:
                            continue

                    for key in keys:
                        try:
                            data = self.redis.get(key)
                            if not data:
                                continue
                            bar = json.loads(data)
                            ts = bar.get('timestamp')

                            # If timestamp found in sorted entries, we can safely delete the individual key
                            if ts in timestamps_in_sorted:
                                candidates.append({'instrument': instrument, 'timeframe': timeframe, 'key': key, 'value': bar})
                                by_instrument[instrument] += 1

                        except Exception as e:
                            logger.warning(f"Failed to parse key {key}: {e}")

            report['candidate_keys'] = len(candidates)
            report['by_instrument'] = by_instrument

            if not candidates:
                logger.info('No legacy candidates found for deletion')
                return report

            # Backup candidates
            backup_path = self.backup_dir / f'legacy_cleanup_backup_{int(time.time())}.json'
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(candidates, f, default=str, indent=2)
            report['backup_path'] = str(backup_path)
            logger.info(f'Backed up {len(candidates)} candidate keys to {backup_path}')

            if dry_run:
                logger.info('Dry-run mode: not deleting keys')
                return report

            # Delete keys
            deleted = 0
            for c in candidates:
                try:
                    self.redis.delete(c['key'])
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete key {c['key']}: {e}")

            report['deleted_keys'] = deleted
            logger.info(f'Deleted {deleted} legacy keys')

        except Exception as e:
            logger.error(f"Legacy cleanup failed: {e}")

        return report



    def _backup_ticks(self, instruments: List[str] = None) -> Dict[str, Any]:
        """Backup tick data."""
        data = {}

        tick_keys = self.redis.keys('tick:*')
        logger.info(f"Found {len(tick_keys)} tick keys to backup")

        for key in tick_keys:
            try:
                parts = key.split(':')
                if len(parts) >= 2:
                    instrument = parts[1]

                    # Filter by instruments if specified
                    if instruments and instrument not in instruments and '*' not in instruments:
                        continue

                    if len(parts) > 2:  # Historical tick
                        timestamp_part = ':'.join(parts[2:])
                        if instrument not in data:
                            data[instrument] = {}
                        value = self.redis.get(key)
                        if value:
                            data[instrument][timestamp_part] = value
                    else:  # Latest tick
                        value = self.redis.get(key)
                        if value:
                            data[instrument] = {'latest': value}

            except Exception as e:
                logger.warning(f"Failed to backup tick key {key}: {e}")

        return data

    def restore_backup(self, backup_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """Restore data from a backup.

        Args:
            backup_id: Backup ID to restore
            dry_run: If True, only validate without restoring

        Returns:
            Restoration report
        """
        logger.info(f"{'Validating' if dry_run else 'Restoring'} backup: {backup_id}")

        # Find backup
        backup_info = self.redis.hget(self.migration_backup_key, backup_id)
        if not backup_info:
            raise ValueError(f"Backup not found: {backup_id}")

        backup_meta = json.loads(backup_info)
        backup_path = Path(backup_meta['path'])

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # Load backup data
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

        report = {
            'backup_id': backup_id,
            'dry_run': dry_run,
            'restored_keys': 0,
            'failed_keys': 0,
            'skipped_keys': 0,
            'errors': []
        }

        try:
            # Restore OHLC data
            if 'ohlc' in backup_data.get('data', {}):
                ohlc_result = self._restore_ohlc_data(backup_data['data']['ohlc'], dry_run)
                report.update(ohlc_result)

            # Restore indicators
            if 'indicators' in backup_data.get('data', {}):
                indicators_result = self._restore_indicators(backup_data['data']['indicators'], dry_run)
                for key, value in indicators_result.items():
                    if key in report:
                        report[key] += value
                    else:
                        report[key] = value

            # Restore ticks
            if 'ticks' in backup_data.get('data', {}):
                ticks_result = self._restore_ticks(backup_data['data']['ticks'], dry_run)
                for key, value in ticks_result.items():
                    if key in report:
                        report[key] += value
                    else:
                        report[key] = value

            # Log migration
            self._log_migration('restore', backup_id, report, dry_run)

            logger.info(f"{'Validation' if dry_run else 'Restoration'} completed: {report}")
            return report

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            report['errors'].append(str(e))
            return report

    def _restore_ohlc_data(self, ohlc_data: Dict[str, Any], dry_run: bool) -> Dict[str, int]:
        """Restore OHLC data."""
        restored = 0
        failed = 0

        for instrument, timeframes in ohlc_data.items():
            for timeframe, data in timeframes.items():
                if isinstance(data, dict):
                    for key_suffix, value in data.items():
                        try:
                            if key_suffix == 'sorted_set':
                                # Restore sorted set (this would be complex, skip for now)
                                continue
                            else:
                                # Restore individual key
                                key = f"ohlc:{instrument}:{timeframe}:{key_suffix}"
                                if not dry_run:
                                    self.redis.setex(key, 86400, value)
                                restored += 1
                        except Exception as e:
                            logger.warning(f"Failed to restore OHLC key {key}: {e}")
                            failed += 1
                else:
                    # Single value
                    try:
                        key = f"ohlc:{instrument}:{timeframe}"
                        if not dry_run:
                            self.redis.setex(key, 86400, data)
                        restored += 1
                    except Exception as e:
                        logger.warning(f"Failed to restore OHLC key {key}: {e}")
                        failed += 1

        return {'restored_keys': restored, 'failed_keys': failed}

    def _restore_indicators(self, indicators_data: Dict[str, Any], dry_run: bool) -> Dict[str, int]:
        """Restore indicators data."""
        restored = 0
        failed = 0

        for instrument, indicators in indicators_data.items():
            for indicator_name, value in indicators.items():
                try:
                    key = f"indicators:{instrument}:{indicator_name}"
                    if not dry_run:
                        self.redis.setex(key, 300, value)
                    restored += 1
                except Exception as e:
                    logger.warning(f"Failed to restore indicator {key}: {e}")
                    failed += 1

        return {'restored_keys': restored, 'failed_keys': failed}

    def _restore_ticks(self, ticks_data: Dict[str, Any], dry_run: bool) -> Dict[str, int]:
        """Restore ticks data."""
        restored = 0
        failed = 0

        for instrument, tick_data in ticks_data.items():
            if isinstance(tick_data, dict):
                for key_suffix, value in tick_data.items():
                    try:
                        if key_suffix == 'latest':
                            key = f"tick:{instrument}:latest"
                        else:
                            key = f"tick:{instrument}:{key_suffix}"

                        if not dry_run:
                            ttl = 3600 if key_suffix != 'latest' else 86400
                            self.redis.setex(key, ttl, value)
                        restored += 1
                    except Exception as e:
                        logger.warning(f"Failed to restore tick key {key}: {e}")
                        failed += 1
            else:
                # Single value
                try:
                    key = f"tick:{instrument}:latest"
                    if not dry_run:
                        self.redis.setex(key, 86400, tick_data)
                    restored += 1
                except Exception as e:
                    logger.warning(f"Failed to restore tick key {key}: {e}")
                    failed += 1

        return {'restored_keys': restored, 'failed_keys': failed}

    def migrate_ohlc_to_standardized(self, instruments: List[str] = None,
                                    dry_run: bool = True) -> Dict[str, Any]:
        """Migrate OHLC data to standardized sorted set format.

        Args:
            instruments: List of instruments to migrate (None for all)
            dry_run: If True, only validate migration without executing

        Returns:
            Migration report
        """
        logger.info(f"Starting OHLC migration (dry_run={dry_run})")

        report = {
            'migration_type': 'ohlc_standardization',
            'dry_run': dry_run,
            'total_keys_processed': 0,
            'keys_migrated': 0,
            'keys_skipped': 0,
            'errors': 0,
            'instruments_processed': []
        }

        try:
            # Find all OHLC keys
            pattern = "ohlc:*" if not instruments else f"ohlc:{instruments[0]}:*"
            all_keys = self.redis.keys(pattern)

            # Group by instrument and timeframe
            instrument_timeframes = {}
            for key in all_keys:
                parts = key.split(':')
                if len(parts) >= 3:
                    instrument = parts[1]
                    timeframe = parts[2]

                    if instruments and instrument not in instruments:
                        continue

                    if instrument not in instrument_timeframes:
                        instrument_timeframes[instrument] = {}
                    if timeframe not in instrument_timeframes[instrument]:
                        instrument_timeframes[instrument][timeframe] = []

                    instrument_timeframes[instrument][timeframe].append(key)

            # Process each instrument/timeframe
            for instrument, timeframes in instrument_timeframes.items():
                report['instruments_processed'].append(instrument)

                for timeframe, keys in timeframes.items():
                    logger.info(f"Migrating {instrument}:{timeframe} ({len(keys)} keys)")

                    migrated_count = 0
                    error_count = 0

                    for key in keys:
                        try:
                            report['total_keys_processed'] += 1

                            # Get data
                            data = self.redis.get(key)
                            if not data:
                                continue

                            # Parse JSON
                            bar_data = json.loads(data)

                            # Use DataStorageManager to store in standardized format
                            # Ensure we import from the package located under market_data/src
                            try:
                                from market_data.data_storage_manager import DataStorageManager
                            except Exception:
                                # Fallback to the nested path if needed
                                from market_data.src.market_data.data_storage_manager import DataStorageManager
                            storage_manager = DataStorageManager(self.redis)

                            if not dry_run:
                                success = storage_manager.store_ohlc_bar(
                                    instrument, timeframe, bar_data, use_sorted_sets=True
                                )
                                if success:
                                    migrated_count += 1
                                    # Mark original key as migrated
                                    bar_data['_migrated'] = True
                                    self.redis.setex(key, 86400, json.dumps(bar_data, default=str))
                                else:
                                    error_count += 1
                            else:
                                # In dry run, just validate
                                migrated_count += 1

                        except Exception as e:
                            logger.warning(f"Failed to migrate key {key}: {e}")
                            error_count += 1

                    logger.info(f"Migrated {migrated_count} keys for {instrument}:{timeframe} (errors: {error_count})")
                    report['keys_migrated'] += migrated_count
                    report['errors'] += error_count

            # Log migration
            self._log_migration('ohlc_migration', None, report, dry_run)

            logger.info(f"Migration completed: {report}")
            return report

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            report['errors'] += 1
            report['error_message'] = str(e)
            return report

    def _log_migration(self, migration_type: str, backup_id: str = None,
                      report: Dict[str, Any] = None, dry_run: bool = False):
        """Log migration operation."""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': migration_type,
            'backup_id': backup_id,
            'dry_run': dry_run,
            'report': report or {}
        }

        # Store in Redis list (keep last 100 migrations)
        self.redis.lpush(self.migration_log_key, json.dumps(log_entry, default=str))
        self.redis.ltrim(self.migration_log_key, 0, 99)

    def get_migration_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get migration history."""
        logs = self.redis.lrange(self.migration_log_key, 0, limit - 1)
        history = []

        for log in logs:
            try:
                history.append(json.loads(log))
            except:
                continue

        return history

    def cleanup_old_backups(self, keep_days: int = 30):
        """Clean up old backup files."""
        cutoff = datetime.now() - timedelta(days=keep_days)

        # Get all backups
        backups = self.redis.hgetall(self.migration_backup_key)

        cleaned = 0
        for backup_id, backup_info_str in backups.items():
            try:
                backup_info = json.loads(backup_info_str)
                backup_time = datetime.fromisoformat(backup_info['timestamp'])

                if backup_time < cutoff:
                    # Remove file
                    backup_path = Path(backup_info['path'])
                    if backup_path.exists():
                        backup_path.unlink()

                    # Remove from Redis
                    self.redis.hdel(self.migration_backup_key, backup_id)
                    cleaned += 1

            except Exception as e:
                logger.warning(f"Failed to cleanup backup {backup_id}: {e}")

        logger.info(f"Cleaned up {cleaned} old backups")
        return cleaned


def main():
    """Main migration utility function."""
    parser = argparse.ArgumentParser(description='Data Migration Utilities')
    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')
    parser.add_argument('--backup-dir', default='./backups', help='Backup directory')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create data backup')
    backup_parser.add_argument('--instruments', nargs='*', help='Instruments to backup')
    backup_parser.add_argument('--types', nargs='*',
                              choices=['ohlc', 'indicators', 'ticks'],
                              default=['ohlc', 'indicators', 'ticks'],
                              help='Data types to backup')

    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_id', help='Backup ID to restore')
    restore_parser.add_argument('--dry-run', action='store_true',
                               help='Validate restore without executing')

    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Migrate data formats')
    migrate_parser.add_argument('--instruments', nargs='*', help='Instruments to migrate')
    migrate_parser.add_argument('--dry-run', action='store_true',
                               help='Validate migration without executing')

    # Cleanup legacy individual keys (dry-run by default, use --confirm to delete)
    cleanup_legacy_parser = subparsers.add_parser('cleanup-legacy', help='Find & delete legacy individual OHLC keys that are already represented in sorted sets')
    cleanup_legacy_parser.add_argument('--instruments', nargs='*', help='Instruments to target')
    cleanup_legacy_parser.add_argument('--confirm', action='store_true', help='Delete candidate keys (default is dry-run)')


    # History command
    history_parser = subparsers.add_parser('history', help='Show migration history')
    history_parser.add_argument('--limit', type=int, default=10, help='Number of entries to show')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old backups')
    cleanup_parser.add_argument('--keep-days', type=int, default=30,
                               help='Keep backups for this many days')

    args = parser.parse_args()

    # Setup Redis connection
    redis_client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=True)

    # Create migration manager
    manager = DataMigrationManager(redis_client, args.backup_dir)

    if args.command == 'backup':
        backup_id = manager.create_backup(args.instruments, args.types)
        print(f"✅ Backup created: {backup_id}")

    elif args.command == 'restore':
        report = manager.restore_backup(args.backup_id, args.dry_run)
        action = "Validated" if args.dry_run else "Restored"
        print(f"✅ {action} backup {args.backup_id}")
        print(f"   Restored: {report.get('restored_keys', 0)}")
        print(f"   Failed: {report.get('failed_keys', 0)}")

    elif args.command == 'migrate':
        report = manager.migrate_ohlc_to_standardized(args.instruments, args.dry_run)
        action = "Validated" if args.dry_run else "Migrated"
        print(f"✅ {action} OHLC data")
        print(f"   Processed: {report.get('total_keys_processed', 0)} keys")
        print(f"   Migrated: {report.get('keys_migrated', 0)} keys")
        print(f"   Errors: {report.get('errors', 0)}")

    elif args.command == 'cleanup-legacy':
        # Delete legacy individual OHLC keys that are already represented in sorted sets
        report = manager.delete_legacy_keys(args.instruments, dry_run=not args.confirm)
        if args.confirm:
            print(f"✅ Deleted legacy keys: {report.get('deleted_keys', 0)} (backed up to {report.get('backup_path')})")
        else:
            print(f"Dry-run: {report.get('candidate_keys', 0)} legacy keys found that could be deleted. Re-run with --confirm to delete.")
            print(f"   Candidates by instrument: {report.get('by_instrument', {})}")

    elif args.command == 'history':
        history = manager.get_migration_history(args.limit)
        print("Migration History:")
        for entry in history:
            timestamp = entry['timestamp'][:19]
            migration_type = entry['type']
            dry_run = "(dry-run)" if entry.get('dry_run') else ""
            print(f"  {timestamp} - {migration_type} {dry_run}")

    elif args.command == 'cleanup':
        cleaned = manager.cleanup_old_backups(args.keep_days)
        print(f"✅ Cleaned up {cleaned} old backups")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()