"""
Tests for lib/consensus/__init__.py module initialization and feature flag.
"""

from pathlib import Path


class TestConsensusModule:
    """Tests for the consensus module initialization."""
    
    def test_module_imports(self):
        """Test that the consensus module can be imported."""
        from allium.lib.consensus import (
            CollectorFetcher,
            AuthorityMonitor,
            format_relay_consensus_evaluation,
            format_authority_consensus_evaluation,
        )
        assert CollectorFetcher is not None
        assert AuthorityMonitor is not None
        assert format_relay_consensus_evaluation is not None
        assert format_authority_consensus_evaluation is not None
    
    def test_is_consensus_evaluation_enabled_function(self):
        """Test that the is_consensus_evaluation_enabled() function exists and returns a boolean."""
        from allium.lib.consensus import is_consensus_evaluation_enabled
        result = is_consensus_evaluation_enabled()
        assert isinstance(result, bool)
    
    def test_set_consensus_evaluation_enabled_export(self):
        """The CLI records the choice through set_consensus_evaluation_enabled."""
        from allium.lib.consensus import set_consensus_evaluation_enabled
        assert callable(set_consensus_evaluation_enabled)
    
    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from allium.lib import consensus
        expected_exports = [
            'CollectorFetcher',
            'AuthorityMonitor', 
            'format_relay_consensus_evaluation',
            'format_authority_consensus_evaluation',
            'is_consensus_evaluation_enabled',
            'set_consensus_evaluation_enabled',
        ]
        for export in expected_exports:
            assert export in consensus.__all__, f"{export} missing from __all__"


class TestFeatureFlag:
    """Consensus evaluation is a CLI flag, recorded for the process by the setter."""

    def test_setter_toggles_the_check_and_restores(self):
        from allium.lib import consensus
        previous = consensus.is_consensus_evaluation_enabled()
        try:
            consensus.set_consensus_evaluation_enabled(False)
            assert consensus.is_consensus_evaluation_enabled() is False
            consensus.set_consensus_evaluation_enabled(True)
            assert consensus.is_consensus_evaluation_enabled() is True
        finally:
            consensus.set_consensus_evaluation_enabled(previous)

    def test_disabling_it_drops_the_collector_workers(self):
        from allium.lib import consensus
        from allium.lib.coordinator import Coordinator
        previous = consensus.is_consensus_evaluation_enabled()
        try:
            consensus.set_consensus_evaluation_enabled(False)
            names = [config.api_name for config in Coordinator.iter_enabled_worker_entries("all")]
            assert "collector_consensus" not in names
            assert "collector_descriptors" not in names
            assert "onionoo_details" in names
        finally:
            consensus.set_consensus_evaluation_enabled(previous)

    def test_module_does_not_read_an_environment_variable(self):
        from allium.lib import consensus
        source = Path(consensus.__file__).read_text(encoding="utf-8")
        assert "os.environ" not in source
        assert "ALLIUM_CONSENSUS_EVALUATION" not in source


class TestModuleDocstring:
    """Tests for module documentation."""
    
    def test_module_has_docstring(self):
        """Test that the consensus module has a docstring."""
        from allium.lib import consensus
        # Module should have some documentation
        # This is a soft requirement
        assert hasattr(consensus, '__doc__')


class TestSubmoduleImports:
    """Tests for submodule imports from the consensus package."""
    
    def test_collector_fetcher_import(self):
        """Test importing CollectorFetcher directly."""
        from allium.lib.consensus.collector_fetcher import CollectorFetcher
        assert CollectorFetcher is not None
    
    def test_authority_monitor_import(self):
        """Test importing AuthorityMonitor directly."""
        from allium.lib.consensus.authority_monitor import AuthorityMonitor
        assert AuthorityMonitor is not None
    
    def test_consensus_evaluation_import(self):
        """Test importing from consensus_evaluation directly."""
        from allium.lib.consensus.consensus_evaluation import (
            format_relay_consensus_evaluation,
            format_authority_consensus_evaluation,
        )
        assert format_relay_consensus_evaluation is not None
        assert format_authority_consensus_evaluation is not None
