# Engine Module Documentation Index

## 📚 Documentation Overview

This directory contains comprehensive documentation for the Engine Module, which orchestrates trading decisions through multiple AI agents and data providers.

## 🗂️ Documentation Structure

### Core Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| **[README.md](../README.md)** | Module overview, installation, and quick start | All users |
| **[DATA_REFERENCE.md](../DATA_REFERENCE.md)** | Complete data structures and API reference | Developers |
| **[API_CONTRACT.md](../API_CONTRACT.md)** | Public API specifications and contracts | Integrators |

### Architecture & Design

| Document | Description | Audience |
|----------|-------------|----------|
| **[AGENTS.md](../AGENTS.md)** | Agent specifications and contracts | Agent developers |
| **[docs/AGENT_API.md](AGENT_API.md)** | Agent interface specifications | Agent implementers |
| **[ENGINE_FLOW_DIAGRAM.md](../ENGINE_FLOW_DIAGRAM.md)** | System architecture and data flow | Architects |
| **[ENGINE_SIGNAL_ANALYSIS.md](../ENGINE_SIGNAL_ANALYSIS.md)** | Signal generation and analysis | Traders/Analysts |

### Planning & Strategy

| Document | Description | Status |
|----------|-------------|--------|
| **[AGENTS_ARCHITECTURE_REDESIGN.md](../AGENTS_ARCHITECTURE_REDESIGN.md)** | Architecture redesign plans | In Progress |
| **[AGENTS_ECOSYSTEM_MASTER_PLAN.md](../AGENTS_ECOSYSTEM_MASTER_PLAN.md)** | Long-term agent ecosystem vision | Planning |

### Archived Documentation

*Located in [docs/archived/](archived/) directory*

| Document | Description | Reason Archived |
|----------|-------------|-----------------|
| **DEPRECATED_README_CONCISE.md** | Old concise README | Replaced by main README |
| **DEPRECATED_AGENT_POSITION_AWARENESS.md** | Old position awareness docs | Consolidated into AGENTS.md |
| **DEPRECATED_STRATEGY_README.md** | Old strategy documentation | Moved to ENGINE_SIGNAL_ANALYSIS.md |
| **DEPRECATED_TEST_UPDATES_SUMMARY.md** | Old test documentation | Integrated into main docs |

## 🚀 Quick Start

### For New Users
1. Start with **[README.md](../README.md)** for installation and basic usage
2. Read **[ENGINE_FLOW_DIAGRAM.md](../ENGINE_FLOW_DIAGRAM.md)** to understand system architecture
3. Check **[AGENTS.md](../AGENTS.md)** for available agents

### For Developers
1. Review **[DATA_REFERENCE.md](../DATA_REFERENCE.md)** for data structures
2. Read **[API_CONTRACT.md](../API_CONTRACT.md)** for integration APIs
3. Check **[docs/AGENT_API.md](AGENT_API.md)** for agent development

### For Traders/Analysts
1. Read **[ENGINE_SIGNAL_ANALYSIS.md](../ENGINE_SIGNAL_ANALYSIS.md)** for signal understanding
2. Review agent-specific documentation in **[AGENTS.md](../AGENTS.md)**

## 🔧 Development Resources

### Code Structure
```
engine_module/
├── src/engine_module/          # Main source code
│   ├── agents/                 # Trading agents
│   ├── contracts/              # Data contracts
│   ├── redis_providers/        # Data providers
│   └── orchestrator/           # Orchestration logic
├── tests/                      # Test suites
└── docs/                       # Documentation
```

### Key Components
- **Agents**: Individual analysis agents (technical, sentiment, etc.)
- **Orchestrator**: Coordinates agent execution and decision synthesis
- **Data Providers**: Fetch data from Redis/external sources
- **Contracts**: Type definitions and interfaces
- **Signal System**: Conditional order generation and monitoring

## 📊 Data Flow

```
Market Data → Redis Cache → Data Providers → Orchestrator → Agents → Decisions → Signals → Execution
```

See **[DATA_REFERENCE.md](../DATA_REFERENCE.md)** for complete data specifications.

## 🔄 Recent Updates

- ✅ **Fixed EnhancedTradingOrchestrator**: Added OHLC data fetching for TechnicalAgent and VolumeAgent
- ✅ **Added Data Providers**: News, Fundamental, and Macro data providers
- ✅ **Created DATA_REFERENCE.md**: Comprehensive data structures documentation
- ✅ **Organized Documentation**: Clean index and structure

## 📞 Support

For questions about:
- **Data structures**: See **[DATA_REFERENCE.md](../DATA_REFERENCE.md)**
- **Agent development**: See **[docs/AGENT_API.md](AGENT_API.md)**
- **System architecture**: See **[ENGINE_FLOW_DIAGRAM.md](../ENGINE_FLOW_DIAGRAM.md)**
- **Integration**: See **[API_CONTRACT.md](../API_CONTRACT.md)**

---

**Last Updated:** January 19, 2026