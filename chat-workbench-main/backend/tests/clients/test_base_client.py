# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for base client and circuit breaker functionality."""

import time
from unittest.mock import MagicMock, patch

import pytest
from app.clients.base import (
    BaseClient,
    CircuitBreaker,
    OperationMonitor,
)
from app.config import Settings


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.mark.unit
    def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initialization with default values."""
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5
        assert cb.reset_timeout == 30
        assert cb.half_open_max_calls == 1
        assert cb.failures == 0
        assert cb.state == 'closed'
        assert cb.half_open_calls == 0

    @pytest.mark.unit
    def test_circuit_breaker_custom_initialization(self):
        """Test CircuitBreaker initialization with custom values."""
        cb = CircuitBreaker(
            failure_threshold=3, reset_timeout=60, half_open_max_calls=2
        )
        assert cb.failure_threshold == 3
        assert cb.reset_timeout == 60
        assert cb.half_open_max_calls == 2

    @pytest.mark.unit
    def test_record_failure_closed_state(self):
        """Test recording failures in closed state."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record failures below threshold
        cb.record_failure()
        assert cb.failures == 1
        assert cb.state == 'closed'

        cb.record_failure()
        assert cb.failures == 2
        assert cb.state == 'closed'

        # This should trigger state change to open
        cb.record_failure()
        assert cb.failures == 3
        assert cb.state == 'open'

    @pytest.mark.unit
    def test_record_failure_half_open_state(self):
        """Test recording failure in half-open state immediately opens circuit."""
        cb = CircuitBreaker()
        cb.state = 'half-open'
        cb.failures = 2

        cb.record_failure()
        assert cb.state == 'open'
        assert cb.failures == 3

    @pytest.mark.unit
    def test_record_success_closed_state(self):
        """Test recording success in closed state resets failures."""
        cb = CircuitBreaker()
        cb.failures = 3
        cb.state = 'closed'

        cb.record_success()
        assert cb.failures == 0
        assert cb.state == 'closed'

    @pytest.mark.unit
    def test_record_success_half_open_state(self):
        """Test recording success in half-open state closes circuit."""
        cb = CircuitBreaker()
        cb.state = 'half-open'
        cb.failures = 3
        cb.half_open_calls = 1

        cb.record_success()
        assert cb.state == 'closed'
        assert cb.failures == 0
        assert cb.half_open_calls == 0

    @pytest.mark.unit
    def test_can_execute_closed_state(self):
        """Test can_execute in closed state."""
        cb = CircuitBreaker()
        assert cb.can_execute() is True

    @pytest.mark.unit
    def test_can_execute_open_state_within_timeout(self):
        """Test can_execute in open state within reset timeout."""
        cb = CircuitBreaker(reset_timeout=30)
        cb.state = 'open'
        cb.last_failure_time = time.time()

        assert cb.can_execute() is False

    @pytest.mark.unit
    def test_can_execute_open_state_after_timeout(self):
        """Test can_execute in open state after reset timeout."""
        cb = CircuitBreaker(reset_timeout=1)  # 1 second timeout
        cb.state = 'open'
        cb.last_failure_time = time.time() - 2  # 2 seconds ago

        result = cb.can_execute()
        assert result is True
        assert cb.state == 'half-open'
        assert cb.half_open_calls == 0

    @pytest.mark.unit
    def test_can_execute_half_open_state_within_limit(self):
        """Test can_execute in half-open state within call limit."""
        cb = CircuitBreaker(half_open_max_calls=2)
        cb.state = 'half-open'
        cb.half_open_calls = 0

        # First call should be allowed
        assert cb.can_execute() is True
        assert cb.half_open_calls == 1

        # Second call should be allowed
        assert cb.can_execute() is True
        assert cb.half_open_calls == 2

        # Third call should be rejected
        assert cb.can_execute() is False

    @pytest.mark.unit
    def test_get_metrics(self):
        """Test circuit breaker metrics collection."""
        cb = CircuitBreaker()
        cb.failures = 2
        cb.state = 'closed'

        metrics = cb.get_metrics()
        assert 'current_state' in metrics
        assert 'current_failures' in metrics
        assert 'success_count' in metrics
        assert 'failure_count' in metrics
        assert metrics['current_state'] == 'closed'
        assert metrics['current_failures'] == 2

    @pytest.mark.unit
    @patch('app.clients.base.set_circuit_breaker_state')
    def test_prometheus_metrics_integration(self, mock_set_state):
        """Test integration with Prometheus metrics."""
        cb = CircuitBreaker()
        cb.client_name = 'test_client'

        # Test failure recording
        cb.record_failure()
        mock_set_state.assert_called_with('test_client', False)

        # Test success recording
        cb.record_success()
        mock_set_state.assert_called_with('test_client', True)


class TestConcreteClient(BaseClient):
    """Concrete implementation of BaseClient for testing."""

    def __init__(self, settings: Settings):
        super().__init__()
        self.initialized = False
        self.cleaned_up = False

    async def initialize(self) -> None:
        """Test initialize implementation."""
        self.initialized = True

    async def cleanup(self) -> None:
        """Test cleanup implementation."""
        self.cleaned_up = True


class TestBaseClient:
    """Tests for BaseClient class."""

    @pytest.fixture
    def test_client(self, test_settings):
        """Create a test client instance."""
        return TestConcreteClient(test_settings)

    @pytest.mark.unit
    def test_base_client_initialization(self, test_client):
        """Test BaseClient initialization."""
        assert test_client.settings is not None
        assert isinstance(test_client.circuit_breaker, CircuitBreaker)
        assert test_client.circuit_breaker.client_name == 'testconcrete'

    @pytest.mark.unit
    async def test_abstract_methods_implemented(self, test_client):
        """Test that concrete client implements abstract methods."""
        await test_client.initialize()
        assert test_client.initialized is True

        await test_client.cleanup()
        assert test_client.cleaned_up is True

    @pytest.mark.unit
    def test_get_client_name(self, test_client):
        """Test client name generation."""
        name = test_client._get_client_name()
        assert name == 'testconcrete'  # Removes 'Client' suffix and lowercases

    @pytest.mark.unit
    def test_monitor_operation(self, test_client):
        """Test operation monitor creation."""
        monitor = test_client.monitor_operation('test_operation')
        assert isinstance(monitor, OperationMonitor)
        assert monitor.operation_name == 'test_operation'
        assert monitor.client == test_client

    @pytest.mark.unit
    def test_get_circuit_breaker_metrics(self, test_client):
        """Test circuit breaker metrics retrieval."""
        metrics = test_client.get_circuit_breaker_metrics()
        assert 'current_state' in metrics
        assert metrics['current_state'] == 'closed'

    @pytest.mark.unit
    def test_check_client_ttl_no_expiration(self, test_client):
        """Test TTL check when client hasn't expired."""
        mock_client = MagicMock()
        creation_time = time.time() - 10  # 10 seconds ago
        ttl_seconds = 60  # 1 minute TTL
        recreate_func = MagicMock()

        result_client, result_time = test_client.check_client_ttl_and_recreate(
            client=mock_client,
            creation_time=creation_time,
            ttl_seconds=ttl_seconds,
            recreate_func=recreate_func,
            client_name='test_client',
        )

        # Should return the same client
        assert result_client == mock_client
        assert result_time == creation_time
        recreate_func.assert_not_called()

    @pytest.mark.unit
    def test_check_client_ttl_expired(self, test_client):
        """Test TTL check when client has expired."""
        old_client = MagicMock()
        new_client = MagicMock()
        creation_time = time.time() - 120  # 2 minutes ago
        ttl_seconds = 60  # 1 minute TTL
        recreate_func = MagicMock(return_value=new_client)

        result_client, result_time = test_client.check_client_ttl_and_recreate(
            client=old_client,
            creation_time=creation_time,
            ttl_seconds=ttl_seconds,
            recreate_func=recreate_func,
            client_name='test_client',
        )

        # Should return the new client
        assert result_client == new_client
        assert result_time > creation_time  # New timestamp
        recreate_func.assert_called_once()

    @pytest.mark.unit
    def test_check_client_ttl_recreate_failure(self, test_client):
        """Test TTL check when recreation fails."""
        old_client = MagicMock()
        creation_time = time.time() - 120  # 2 minutes ago
        ttl_seconds = 60  # 1 minute TTL
        recreate_func = MagicMock(side_effect=Exception('Recreation failed'))

        with pytest.raises(Exception, match='Recreation failed'):
            test_client.check_client_ttl_and_recreate(
                client=old_client,
                creation_time=creation_time,
                ttl_seconds=ttl_seconds,
                recreate_func=recreate_func,
                client_name='test_client',
            )

        # Should record failure in circuit breaker
        assert test_client.circuit_breaker.failures == 1


class TestOperationMonitor:
    """Tests for OperationMonitor context manager."""

    @pytest.fixture
    def test_client(self, test_settings):
        """Create a test client for monitoring tests."""
        return TestConcreteClient(test_settings)

    @pytest.mark.unit
    @patch('app.clients.base.RequestContext.get_state')
    def test_operation_monitor_initialization(self, mock_get_state, test_client):
        """Test OperationMonitor initialization."""
        # Mock request state
        mock_state = MagicMock()
        mock_state.request_id = 'req_123'
        mock_state.chat_id = 'chat_456'
        mock_state.user_id = 'user_789'
        mock_get_state.return_value = mock_state

        monitor = OperationMonitor(test_client, 'test_operation')
        assert monitor.client == test_client
        assert monitor.operation_name == 'test_operation'
        assert monitor.request_id == 'req_123'
        assert monitor.chat_id == 'chat_456'
        assert monitor.user_id == 'user_789'

    @pytest.mark.unit
    @patch('app.clients.base.RequestContext.get_state')
    @patch('app.clients.base.track_client_request')
    def test_operation_monitor_success(
        self, mock_track_request, mock_get_state, test_client
    ):
        """Test OperationMonitor with successful operation."""
        # Mock request state
        mock_state = MagicMock()
        mock_state.request_id = 'req_123'
        mock_state.chat_id = None
        mock_state.user_id = None
        mock_get_state.return_value = mock_state

        with test_client.monitor_operation('test_op'):
            time.sleep(0.01)  # Small delay to measure duration

        # Should track successful request
        mock_track_request.assert_called_once()
        call_args = mock_track_request.call_args[0]
        assert call_args[0] == 'testconcrete'  # client name
        assert call_args[1] == 'test_op'  # operation name
        assert call_args[2] == 'success'  # status
        assert call_args[3] > 0  # duration

        # Should record success in circuit breaker
        assert test_client.circuit_breaker.metrics['success_count'] == 1

    @pytest.mark.unit
    @patch('app.clients.base.RequestContext.get_state')
    @patch('app.clients.base.track_client_error')
    def test_operation_monitor_failure(
        self, mock_track_error, mock_get_state, test_client
    ):
        """Test OperationMonitor with failed operation."""
        # Mock request state
        mock_state = MagicMock()
        mock_state.request_id = 'req_123'
        mock_state.chat_id = 'chat_456'
        mock_state.user_id = 'user_789'
        mock_get_state.return_value = mock_state

        with pytest.raises(
            ValueError, match='Test error'
        ) and test_client.monitor_operation('test_op'):
            raise ValueError('Test error')

        # Should track error
        mock_track_error.assert_called_once_with(
            'testconcrete', 'test_op', 'ValueError'
        )

        # Should record failure in circuit breaker
        assert test_client.circuit_breaker.failures == 1

    @pytest.mark.unit
    @patch('app.clients.base.RequestContext.get_state')
    def test_operation_monitor_context_data(self, mock_get_state, test_client):
        """Test that OperationMonitor captures request context correctly."""
        # Mock request state with all fields
        mock_state = MagicMock()
        mock_state.request_id = 'req_123'
        mock_state.chat_id = 'chat_456'
        mock_state.user_id = 'user_789'
        mock_get_state.return_value = mock_state

        monitor = OperationMonitor(test_client, 'test_operation')

        assert monitor.request_id == 'req_123'
        assert monitor.chat_id == 'chat_456'
        assert monitor.user_id == 'user_789'
        assert monitor.client_name == 'testconcrete'


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with clients."""

    @pytest.fixture
    def test_client(self, test_settings):
        """Create a test client for integration tests."""
        return TestConcreteClient(test_settings)

    @pytest.mark.unit
    @patch('app.clients.base.RequestContext.get_state')
    def test_circuit_breaker_opens_after_failures(self, mock_get_state, test_client):
        """Test that circuit breaker opens after threshold failures."""
        # Configure circuit breaker with low threshold
        test_client.circuit_breaker.failure_threshold = 2

        # Mock request state
        mock_state = MagicMock()
        mock_state.request_id = 'req_123'
        mock_state.chat_id = None
        mock_state.user_id = None
        mock_get_state.return_value = mock_state

        # Generate failures
        for i in range(2):
            with pytest.raises(RuntimeError) and test_client.monitor_operation(
                'failing_op'
            ):
                raise RuntimeError(f'Failure {i + 1}')

        # Circuit should now be open
        assert test_client.circuit_breaker.state == 'open'
        assert test_client.circuit_breaker.failures == 2

    @pytest.mark.unit
    @patch('app.clients.base.RequestContext.get_state')
    def test_circuit_breaker_half_open_recovery(self, mock_get_state, test_client):
        """Test circuit breaker recovery through half-open state."""
        # Configure circuit breaker with short timeout
        test_client.circuit_breaker.failure_threshold = 1
        test_client.circuit_breaker.reset_timeout = 0.1  # 100ms

        # Mock request state
        mock_state = MagicMock()
        mock_state.request_id = 'req_123'
        mock_state.chat_id = None
        mock_state.user_id = None
        mock_get_state.return_value = mock_state

        # Trigger circuit open
        with pytest.raises(RuntimeError) and test_client.monitor_operation(
            'failing_op'
        ):
            raise RuntimeError('Initial failure')

        assert test_client.circuit_breaker.state == 'open'

        # Wait for reset timeout
        time.sleep(0.2)

        # Check that circuit can execute (should transition to half-open)
        can_execute = test_client.circuit_breaker.can_execute()
        assert can_execute is True
        assert test_client.circuit_breaker.state == 'half-open'

        # Successful operation should close circuit
        with test_client.monitor_operation('successful_op'):
            pass  # Successful operation

        assert test_client.circuit_breaker.state == 'closed'
        assert test_client.circuit_breaker.failures == 0

    @pytest.mark.slow
    @pytest.mark.unit
    @patch('app.clients.base.RequestContext.get_state')
    def test_circuit_breaker_concurrent_operations(self, mock_get_state, test_client):
        """Test circuit breaker behavior under concurrent operations."""
        import threading

        # Mock request state
        mock_state = MagicMock()
        mock_state.request_id = 'req_123'
        mock_state.chat_id = None
        mock_state.user_id = None
        mock_get_state.return_value = mock_state

        # Configure circuit breaker
        test_client.circuit_breaker.failure_threshold = 5

        # Using lists to store counts (mutable)
        success_count = [0]
        failure_count = [0]

        def simulate_operation(should_fail=False):
            try:
                with test_client.monitor_operation('concurrent_op'):
                    if should_fail:
                        raise RuntimeError('Simulated failure')
                success_count[0] += 1
            except RuntimeError:
                failure_count[0] += 1

        # Run concurrent operations
        threads = []
        for i in range(10):
            should_fail = i < 3  # First 3 operations fail
            thread = threading.Thread(target=simulate_operation, args=(should_fail,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        assert failure_count[0] == 3
        assert success_count[0] == 7
        # Circuit should still be closed since failures < threshold
        assert test_client.circuit_breaker.state == 'closed'
