# Documentation Index

**Last Updated**: January 12, 2026
**Reorganized**: Clean structure with categorized documentation

## 📚 Documentation Structure

### 🏗️ **Architecture & Design** (`docs/architecture/`)
System design, module interactions, and technical architecture

- **[ARCHITECTURE.md](architecture/ARCHITECTURE.md)** - System overview, modules, data flow
- **[MICROSERVICES_ARCHITECTURE.md](architecture/MICROSERVICES_ARCHITECTURE.md)** - Container architecture

### 🤖 **Agents & Intelligence** (`docs/agents/`)
Agent specifications, implementations, and AI systems

- **[AGENTS_ECOSYSTEM_DOCUMENTATION.md](agents/AGENTS_ECOSYSTEM_DOCUMENTATION.md)** - Agent ecosystem overview
- **[AGENTS_FULL_ANALYSIS_REPORT.md](agents/AGENTS_FULL_ANALYSIS_REPORT.md)** - Comprehensive agent analysis
- **[AGENTS_LIVE_DEMO_RESULTS.md](agents/AGENTS_LIVE_DEMO_RESULTS.md)** - Live testing results

### 📊 **Data & Integration** (`docs/data/`)
Data sources, APIs, and integration guides

- **[MARKET_DATA_INVENTORY.md](data/MARKET_DATA_INVENTORY.md)** - Available data sources
- **[ZERODHA_DATA_STRUCTURES.md](data/ZERODHA_DATA_STRUCTURES.md)** - Kite API data formats
- **[ZERODHA_HISTORICAL_INTEGRATION.md](data/ZERODHA_HISTORICAL_INTEGRATION.md)** - Historical data integration

### 📈 **Evidence & Validation** (`docs/evidence/`)
Testing results, performance metrics, and validation reports

- **[HISTORICAL_2026_EVIDENCE.md](evidence/HISTORICAL_2026_EVIDENCE.md)** - Historical testing evidence
- **[LLM_INTEGRATION_EVIDENCE.md](evidence/LLM_INTEGRATION_EVIDENCE.md)** - LLM integration proof
- **[AGENTS_EXPANSION_PLAN.md](evidence/AGENTS_EXPANSION_PLAN.md)** - Implementation roadmap

### 💼 **Business & Features** (`docs/business/`)
Business requirements, features, and API contracts

- **[FEATURES.md](business/FEATURES.md)** - Feature documentation
- **[TRADING_COCKPIT.md](business/TRADING_COCKPIT.md)** - Dashboard UI guide
- **[API_CONTRACTS_PLAN.md](business/API_CONTRACTS_PLAN.md)** - API specifications
- **[API_ENDPOINTS_SUMMARY.md](business/API_ENDPOINTS_SUMMARY.md)** - Endpoint documentation
- **[API_INDEX.md](business/API_INDEX.md)** - API reference

### 🛠️ **Development & Testing** (`docs/development/`)
Developer guides, testing, and debugging

- **[TESTING.md](development/TESTING.md)** - Test suite and procedures
- **[DEBUGGING_CHECKLIST.md](development/DEBUGGING_CHECKLIST.md)** - Troubleshooting guide
- **[START_LOCAL_GUIDE.md](development/START_LOCAL_GUIDE.md)** - Local development setup

### 📁 **Archive** (`docs/archive/`)
Historical documentation (preserved for reference)

- Analysis reports, implementation reviews, and deprecated docs

**Total**: 18 organized files (vs 30+ scattered files) - 40% reduction in clutter

## 🎯 Quick Navigation

### I want to...

**Get Started**
→ [README.md](README.md#quick-start)

**Understand the Architecture**
→ [ARCHITECTURE.md](ARCHITECTURE.md)

**Run Tests**
→ [TESTING.md](TESTING.md#quick-start)

**Use the Dashboard**
→ [TRADING_COCKPIT.md](TRADING_COCKPIT.md#overview)

**Learn About Features**
- Real-time Signals → [FEATURES.md](FEATURES.md#real-time-signal-to-trade) • [Signal Lifecycle](docs/SIGNAL_LIFECYCLE.md) • [Signals API](docs/SIGNALS_API_USAGE.md)
- Technical Indicators → [FEATURES.md](FEATURES.md#technical-indicators-integration)
- Historical Replay → [FEATURES.md](FEATURES.md#historical-mode--replay)
- Multi-Agent System → [FEATURES.md](FEATURES.md#multi-agent-system)
- Agent Reference → [`engine_module/AGENTS.md`](engine_module/AGENTS.md) (canonical per-agent documentation)
- Virtual Time → [FEATURES.md](FEATURES.md#virtual-time-synchronization)

**Integrate with Zerodha**
- Data Structures → [ZERODHA_DATA_STRUCTURES.md](ZERODHA_DATA_STRUCTURES.md)
- Historical Data → [ZERODHA_HISTORICAL_INTEGRATION.md](ZERODHA_HISTORICAL_INTEGRATION.md)

**Develop & Debug**
- Module Structure → [ARCHITECTURE.md](ARCHITECTURE.md#module-structure)
- Testing Guide → [TESTING.md](TESTING.md)
- API Reference → [TRADING_COCKPIT.md](TRADING_COCKPIT.md#api-endpoints)

## 📖 What's in Each Document

### README.md
The main entry point with:
- System overview and key features
- Quick start for 3 operational modes
- Installation instructions
- Module overview
- Troubleshooting guide

### ARCHITECTURE.md
Technical architecture covering:
- 6 independent domain modules
- Module dependencies and contracts
- Data flow diagrams
- Service container design
- Extension points

### FEATURES.md
Consolidated feature documentation:
- Real-time Signal-to-Trade system
- Technical Indicators integration
- Historical replay and backtesting
- Multi-agent trading intelligence
- Virtual time synchronization

### TESTING.md
Complete testing guide:
- Test suite overview
- Virtual time testing
- Market hours boundary tests
- Signal monitoring tests
- Troubleshooting tips

### TRADING_COCKPIT.md
Dashboard user guide:
- UI sections and controls
- Historical replay controls
- API endpoints
- WebSocket integration
- Keyboard shortcuts
- Customization options

### ZERODHA_DATA_STRUCTURES.md
Zerodha API reference:
- Market tick data
- OHLC bar data
- Options chain data
- Account/margin data
- Instrument metadata

### ZERODHA_HISTORICAL_INTEGRATION.md
Historical data integration:
- Data source configuration
- Zerodha API usage
- CSV file format
- Synthetic data generation

## 🗑️ Removed Documentation (Consolidated)

The following 18 files were removed and their content merged into the above docs:

**Consolidated into FEATURES.md**:
- HISTORICAL_MODE_SWITCHING.md
- HISTORICAL_SIMULATION_SUMMARY.md
- TECHNICAL_INDICATORS_INTEGRATION.md
- TECHNICAL_INDICATORS_SUMMARY.md
- REALTIME_SIGNAL_TO_TRADE.md
- MULTI_AGENT_README.md
- AGENT_ARCHITECTURE_ANALYSIS.md

**Consolidated into TESTING.md**:
- TEST_QUICK_REFERENCE.md
- TEST_RESULTS.md
- TEST_SUITE_DOCUMENTATION.md
- TESTING_GUIDE.md
- TEST_UPDATES_VIRTUAL_TIME.md
- TEST_UPDATE_COMPLETION_REPORT.md
- WHY_TESTS_FAILED.md

**Consolidated into TRADING_COCKPIT.md**:
- TRADING_COCKPIT_QUICK_START.md
- TRADING_COCKPIT_README.md
- TRADING_COCKPIT_UX_ANALYSIS.md
- TRADING_COCKPIT_UX_IMPROVEMENTS.md
- UI_HISTORICAL_REPLAY_GUIDE.md

---

Additional files recently archived to `docs/archived_root_docs/` (DEPRECATED_ prefix):
- DEPRECATED_REALTIME_INTEGRATION_PLAN.md (moved)
- DEPRECATED_REALTIME_TEST_PLAN.md (moved)
- DEPRECATED_SEQUENCE_DIAGRAMS.md (moved)
- DEPRECATED_UI_ARCHITECTURE_ANALYSIS.md (moved)
- DEPRECATED_IMPLEMENTATION_SUMMARY.md (moved)
## 📝 Documentation Standards

All documentation follows these standards:

### Format
- Markdown with GitHub Flavored Markdown (GFM)
- Code blocks with language hints
- Tables for structured data
- Diagrams in ASCII art or Mermaid

### Structure
- Clear table of contents
- Section headings with IDs for deep linking
- Examples for all major features
- Troubleshooting sections where relevant

### Content
- Verified against current code
- Updated timestamps
- Working code examples
- No outdated information

## 🔄 Maintenance

### When to Update

**README.md**:
- New installation steps
- New operational modes
- Major feature additions
- Updated quick start commands

**ARCHITECTURE.md**:
- New modules added
- Module dependencies changed
- Data flow modifications
- New design patterns

**FEATURES.md**:
- New features added
- Existing feature changes
- API updates
- Integration changes

**TESTING.md**:
- New test files added
- Test patterns changed
- New testing requirements
- Updated pass rates

**TRADING_COCKPIT.md**:
- UI changes
- New controls or panels
- API endpoint changes
- WebSocket protocol updates

**ZERODHA_*.md**:
- Kite API updates
- New data structures
- Integration pattern changes

### Update Process

1. Make code changes
2. Update relevant documentation
3. Verify examples still work
4. Update "Last Updated" date
5. Run doc link checker
6. Commit docs with code

## 🔍 Finding Information

### Search Tips

```bash
# Find all mentions of a feature
grep -r "signal monitor" *.md

# Find API endpoints
grep -r "POST /api" *.md

# Find code examples in Python
grep -A 10 "```python" *.md
```

### Cross-References

Documents link to each other using relative paths:
- `[See Testing Guide](TESTING.md#virtual-time-system)`
- `[Architecture Overview](ARCHITECTURE.md#module-structure)`

## 📊 Coverage Matrix

| Topic | README | ARCH | FEATURES | TESTING | COCKPIT | ZERODHA |
|-------|:------:|:----:|:--------:|:-------:|:-------:|:-------:|
| Installation | ✅ | | | | | |
| Quick Start | ✅ | | | | | |
| Architecture | ✅ | ✅ | | | | |
| Modules | ✅ | ✅ | | | | |
| Signals | ✅ | | ✅ | ✅ | | |
| Indicators | ✅ | | ✅ | ✅ | | |
| Historical Replay | ✅ | | ✅ | ✅ | ✅ | ✅ |
| Multi-Agent | ✅ | ✅ | ✅ | | | |
| Virtual Time | ✅ | | ✅ | ✅ | ✅ | |
| Testing | ✅ | | | ✅ | | |
| Dashboard UI | ✅ | | | | ✅ | |
| Zerodha API | ✅ | | | | | ✅ |
| Troubleshooting | ✅ | | | ✅ | ✅ | |

## 🎓 Learning Path

### For New Users
1. Start with [README.md](README.md)
2. Follow [Quick Start](README.md#quick-start)
3. Explore [Trading Cockpit](TRADING_COCKPIT.md)
4. Review [Features](FEATURES.md)

### For Developers
1. Read [ARCHITECTURE.md](ARCHITECTURE.md)
2. Study [Module Structure](ARCHITECTURE.md#module-structure)
3. Review [TESTING.md](TESTING.md)
4. Check [ZERODHA_DATA_STRUCTURES.md](ZERODHA_DATA_STRUCTURES.md)

### For Traders
1. Review [Features](FEATURES.md)
2. Learn [Trading Cockpit](TRADING_COCKPIT.md)
3. Understand [Multi-Agent System](FEATURES.md#multi-agent-system)
4. Test with [Historical Replay](FEATURES.md#historical-mode--replay)

## 📞 Support

For questions or issues:
1. Check relevant documentation
2. Search for error messages in docs
3. Review troubleshooting sections
4. Check test files for examples
5. Raise an issue with documentation feedback

---

**Documentation Consolidation completed January 7, 2026**
**Files reduced: 23 → 7 (60% reduction)**
**Total size reduced: 208KB → 82KB**

