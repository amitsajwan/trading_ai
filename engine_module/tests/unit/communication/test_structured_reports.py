"""Unit tests for Structured Reports."""

import pytest
from datetime import datetime
from engine_module.communication.structured_reports import (
    StructuredReport,
    ReportSection,
    ReportEvidence,
    ReportAction,
    ReportBuilder,
    ReportType,
    ReportPriority,
    EvidenceType
)


class TestReportEvidence:
    """Tests for ReportEvidence."""
    
    def test_evidence_creation(self):
        """Test ReportEvidence creation."""
        evidence = ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI shows oversold condition",
            value=28.5,
            source="RSI_14",
            confidence=0.85
        )
        
        assert evidence.type == EvidenceType.TECHNICAL_INDICATOR
        assert evidence.description == "RSI shows oversold condition"
        assert evidence.value == 28.5
        assert evidence.source == "RSI_14"
        assert evidence.confidence == 0.85
        assert evidence.timestamp is not None
    
    def test_evidence_confidence_clamping(self):
        """Test confidence clamping to [0.0, 1.0]."""
        evidence = ReportEvidence(
            type=EvidenceType.MARKET_DATA,
            description="Test",
            value=100.0,
            source="test",
            confidence=1.5  # Above 1.0
        )
        assert evidence.confidence == 1.0
        
        evidence2 = ReportEvidence(
            type=EvidenceType.MARKET_DATA,
            description="Test",
            value=100.0,
            source="test",
            confidence=-0.5  # Below 0.0
        )
        assert evidence2.confidence == 0.0
    
    def test_evidence_to_dict(self):
        """Test evidence serialization."""
        evidence = ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI oversold",
            value=28.5,
            source="RSI_14",
            confidence=0.85
        )
        
        evidence_dict = evidence.to_dict()
        assert evidence_dict['type'] == 'technical_indicator'
        assert evidence_dict['value'] == 28.5
        assert evidence_dict['confidence'] == 0.85


class TestReportSection:
    """Tests for ReportSection."""
    
    def test_section_creation(self):
        """Test ReportSection creation."""
        section = ReportSection(
            title="Technical Analysis",
            content="RSI indicates oversold conditions",
            confidence=0.75
        )
        
        assert section.title == "Technical Analysis"
        assert section.content == "RSI indicates oversold conditions"
        assert section.confidence == 0.75
        assert len(section.evidence) == 0
        assert len(section.subsections) == 0
    
    def test_section_add_evidence(self):
        """Test adding evidence to section."""
        section = ReportSection(
            title="Technical Analysis",
            content="Analysis content"
        )
        
        evidence = ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI oversold",
            value=28.5,
            source="RSI_14"
        )
        
        section.add_evidence(evidence)
        assert len(section.evidence) == 1
        assert section.evidence[0].value == 28.5
    
    def test_section_add_subsection(self):
        """Test adding subsection."""
        section = ReportSection(
            title="Main Section",
            content="Main content"
        )
        
        subsection = ReportSection(
            title="Sub Section",
            content="Sub content"
        )
        
        section.add_subsection(subsection)
        assert len(section.subsections) == 1
        assert section.subsections[0].title == "Sub Section"


class TestReportAction:
    """Tests for ReportAction."""
    
    def test_action_creation(self):
        """Test ReportAction creation."""
        action = ReportAction(
            action="BUY",
            target="BANKNIFTY",
            quantity=25.0,
            reasoning="RSI oversold, bullish reversal expected",
            confidence=0.80
        )
        
        assert action.action == "BUY"
        assert action.target == "BANKNIFTY"
        assert action.quantity == 25.0
        assert action.confidence == 0.80
    
    def test_action_to_dict(self):
        """Test action serialization."""
        action = ReportAction(
            action="SELL",
            target="BANKNIFTY",
            reasoning="Overbought conditions",
            confidence=0.70
        )
        
        action_dict = action.to_dict()
        assert action_dict['action'] == "SELL"
        assert action_dict['target'] == "BANKNIFTY"
        assert action_dict['confidence'] == 0.70


class TestStructuredReport:
    """Tests for StructuredReport."""
    
    def test_report_creation(self):
        """Test StructuredReport creation."""
        report = StructuredReport(
            agent_name="TechnicalAgent",
            report_type=ReportType.ANALYSIS,
            priority=ReportPriority.HIGH,
            title="Technical Analysis Report",
            summary="RSI indicates oversold conditions",
            confidence=0.75
        )
        
        assert report.agent_name == "TechnicalAgent"
        assert report.report_type == ReportType.ANALYSIS
        assert report.priority == ReportPriority.HIGH
        assert report.title == "Technical Analysis Report"
        assert report.summary == "RSI indicates oversold conditions"
        assert report.confidence == 0.75
        assert report.timestamp is not None
    
    def test_report_add_section(self):
        """Test adding section to report."""
        report = StructuredReport(
            agent_name="TechnicalAgent",
            report_type=ReportType.ANALYSIS,
            priority=ReportPriority.MEDIUM,
            title="Test Report",
            summary="Test summary"
        )
        
        section = ReportSection(
            title="Analysis",
            content="Content here"
        )
        
        report.add_section(section)
        assert len(report.sections) == 1
        assert report.sections[0].title == "Analysis"
    
    def test_report_add_action(self):
        """Test adding action to report."""
        report = StructuredReport(
            agent_name="TechnicalAgent",
            report_type=ReportType.RECOMMENDATION,
            priority=ReportPriority.HIGH,
            title="Recommendation Report",
            summary="Buy recommendation"
        )
        
        action = ReportAction(
            action="BUY",
            target="BANKNIFTY",
            reasoning="Strong buy signal"
        )
        
        report.add_action(action)
        assert len(report.actions) == 1
        assert report.actions[0].action == "BUY"
    
    def test_report_get_overall_confidence(self):
        """Test overall confidence calculation."""
        report = StructuredReport(
            agent_name="TechnicalAgent",
            report_type=ReportType.ANALYSIS,
            priority=ReportPriority.MEDIUM,
            title="Test Report",
            summary="Test",
            confidence=0.6
        )
        
        # Add section with confidence
        section = ReportSection(
            title="Analysis",
            content="Content",
            confidence=0.8
        )
        report.add_section(section)
        
        # Add action with confidence
        action = ReportAction(
            action="BUY",
            target="BANKNIFTY",
            confidence=0.7
        )
        report.add_action(action)
        
        # Overall confidence should be weighted average
        overall = report.get_overall_confidence()
        assert 0.0 <= overall <= 1.0
        assert overall >= 0.6  # Should be at least base confidence
    
    def test_report_to_dict(self):
        """Test report serialization."""
        report = StructuredReport(
            agent_name="TechnicalAgent",
            report_type=ReportType.ANALYSIS,
            priority=ReportPriority.HIGH,
            title="Test Report",
            summary="Test summary"
        )
        
        report_dict = report.to_dict()
        assert report_dict['agent_name'] == "TechnicalAgent"
        assert report_dict['report_type'] == "analysis"
        assert report_dict['priority'] == "high"
        assert report_dict['title'] == "Test Report"
        assert 'timestamp' in report_dict
    
    def test_report_to_markdown(self):
        """Test report markdown conversion."""
        report = StructuredReport(
            agent_name="TechnicalAgent",
            report_type=ReportType.ANALYSIS,
            priority=ReportPriority.HIGH,
            title="Technical Analysis",
            summary="RSI indicates oversold"
        )
        
        section = ReportSection(
            title="RSI Analysis",
            content="RSI is at 28.5, indicating oversold conditions",
            confidence=0.85
        )
        
        evidence = ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI oversold",
            value=28.5,
            source="RSI_14",
            confidence=0.85
        )
        section.add_evidence(evidence)
        report.add_section(section)
        
        action = ReportAction(
            action="BUY",
            target="BANKNIFTY",
            reasoning="Oversold bounce expected",
            confidence=0.80
        )
        report.add_action(action)
        
        markdown = report.to_markdown()
        assert "# Technical Analysis" in markdown
        assert "TechnicalAgent" in markdown
        assert "## Summary" in markdown
        assert "## RSI Analysis" in markdown
        assert "### Evidence" in markdown
        assert "## Recommended Actions" in markdown


class TestReportBuilder:
    """Tests for ReportBuilder."""
    
    def test_builder_creation(self):
        """Test ReportBuilder creation."""
        builder = ReportBuilder("TechnicalAgent")
        assert builder.agent_name == "TechnicalAgent"
    
    def test_builder_fluent_interface(self):
        """Test fluent builder interface."""
        builder = ReportBuilder("TechnicalAgent")
        report = (builder
                 .set_type(ReportType.ANALYSIS)
                 .set_priority(ReportPriority.HIGH)
                 .set_title("Test Report")
                 .set_summary("Test summary")
                 .set_confidence(0.75)
                 .build())
        
        assert report.agent_name == "TechnicalAgent"
        assert report.report_type == ReportType.ANALYSIS
        assert report.priority == ReportPriority.HIGH
        assert report.title == "Test Report"
        assert report.summary == "Test summary"
        assert report.confidence == 0.75
    
    def test_builder_add_section(self):
        """Test adding section via builder."""
        builder = ReportBuilder("TechnicalAgent")
        evidence = ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI oversold",
            value=28.5,
            source="RSI_14"
        )
        
        report = (builder
                 .set_title("Test")
                 .set_summary("Summary")
                 .add_section(
                     title="Analysis",
                     content="Content",
                     confidence=0.8,
                     evidence=[evidence]
                 )
                 .build())
        
        assert len(report.sections) == 1
        assert report.sections[0].title == "Analysis"
        assert len(report.sections[0].evidence) == 1
    
    def test_builder_add_action(self):
        """Test adding action via builder."""
        builder = ReportBuilder("TechnicalAgent")
        report = (builder
                 .set_title("Test")
                 .set_summary("Summary")
                 .add_action(
                     action="BUY",
                     target="BANKNIFTY",
                     reasoning="Strong signal",
                     confidence=0.85
                 )
                 .build())
        
        assert len(report.actions) == 1
        assert report.actions[0].action == "BUY"
        assert report.actions[0].target == "BANKNIFTY"
        assert report.actions[0].confidence == 0.85
    
    def test_builder_default_title(self):
        """Test default title generation."""
        builder = ReportBuilder("TechnicalAgent")
        builder.set_type(ReportType.ANALYSIS)
        builder.set_summary("Summary")
        report = builder.build()
        
        assert report.title == "Analysis Report"  # Type + "Report"
    
    def test_builder_add_evidence_to_last_section(self):
        """Test adding evidence to last section."""
        builder = ReportBuilder("TechnicalAgent")
        evidence = ReportEvidence(
            type=EvidenceType.TECHNICAL_INDICATOR,
            description="RSI oversold",
            value=28.5,
            source="RSI_14"
        )
        
        report = (builder
                 .set_title("Test")
                 .set_summary("Summary")
                 .add_section(title="Analysis", content="Content")
                 .add_evidence_to_last_section(evidence)
                 .build())
        
        assert len(report.sections) == 1
        assert len(report.sections[0].evidence) == 1
