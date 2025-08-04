# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for monitoring module."""

from unittest.mock import patch

import pytest
from app.monitoring import (
    CHAT_LATENCY,
    CHAT_MESSAGE_COUNT,
    CHAT_TOKEN_COUNT,
    CIRCUIT_BREAKER_STATE,
    CLIENT_ERRORS,
    CLIENT_REQUEST_COUNT,
    CLIENT_REQUEST_LATENCY,
    CONTEXT_SERVER_ERROR_COUNT,
    CONTEXT_SERVER_LATENCY,
    CONTEXT_SERVER_QUERY_COUNT,
    LLM_COST,
    LLM_ERROR_COUNT,
    LLM_RATE_LIMIT_REMAINING,
    LLM_REQUEST_COUNT,
    LLM_REQUEST_LATENCY,
    LLM_TOKEN_USAGE,
    OPERATION_COUNT,
    OPERATION_LATENCY,
    OperationMonitor,
    set_circuit_breaker_state,
    track_chat_message,
    track_client_error,
    track_client_request,
    track_context_server_error,
    track_context_server_latency,
    track_context_server_query,
    track_llm_error,
    track_model_request,
    track_model_usage,
)


class TestPrometheusMetrics:
    """Test Prometheus metrics are properly defined."""

    def test_metrics_exist(self):
        """Test that all metrics are properly defined."""
        # Operation metrics
        assert OPERATION_LATENCY is not None
        assert OPERATION_COUNT is not None

        # Client metrics
        assert CLIENT_REQUEST_COUNT is not None
        assert CLIENT_REQUEST_LATENCY is not None
        assert CLIENT_ERRORS is not None
        assert CIRCUIT_BREAKER_STATE is not None

        # Chat metrics
        assert CHAT_MESSAGE_COUNT is not None
        assert CHAT_TOKEN_COUNT is not None
        assert CHAT_LATENCY is not None

        # LLM metrics
        assert LLM_TOKEN_USAGE is not None
        assert LLM_REQUEST_COUNT is not None
        assert LLM_REQUEST_LATENCY is not None
        assert LLM_ERROR_COUNT is not None
        assert LLM_COST is not None
        assert LLM_RATE_LIMIT_REMAINING is not None

        # Context server metrics
        assert CONTEXT_SERVER_QUERY_COUNT is not None
        assert CONTEXT_SERVER_LATENCY is not None
        assert CONTEXT_SERVER_ERROR_COUNT is not None

    def test_metric_labels(self):
        """Test that metrics have expected labels."""
        # Test a few key metrics have the right label names
        assert OPERATION_LATENCY._labelnames == ('service', 'operation', 'success')
        assert CLIENT_REQUEST_COUNT._labelnames == ('client', 'operation', 'status')
        assert LLM_TOKEN_USAGE._labelnames == ('model', 'token_type')
        assert CONTEXT_SERVER_QUERY_COUNT._labelnames == ('server', 'operation')


class TestOperationMonitor:
    """Test OperationMonitor class."""

    def test_operation_monitor_init(self):
        """Test OperationMonitor initialization."""
        monitor = OperationMonitor('test-service')
        assert monitor.service_name == 'test-service'

    def test_operation_context_manager_success(self):
        """Test operation context manager with successful operation."""
        monitor = OperationMonitor('test-service')

        with patch.object(monitor, '_record_metrics') as mock_record:
            with monitor.operation('test-op'):
                pass  # Successful operation

            # Verify metrics were recorded
            mock_record.assert_called_once()
            args, kwargs = mock_record.call_args
            operation_name, duration, success, extra_labels = args

            assert operation_name == 'test-op'
            assert isinstance(duration, float)
            assert duration >= 0
            assert success is True
            assert extra_labels is None

    def test_operation_context_manager_failure(self):
        """Test operation context manager with failed operation."""
        monitor = OperationMonitor('test-service')

        with patch.object(monitor, '_record_metrics') as mock_record:
            with pytest.raises(ValueError), monitor.operation('test-op'):
                raise ValueError('Test error')

            # Verify metrics were recorded with failure
            mock_record.assert_called_once()
            args, kwargs = mock_record.call_args
            operation_name, duration, success, extra_labels = args

            assert operation_name == 'test-op'
            assert isinstance(duration, float)
            assert success is False

    def test_operation_with_extra_labels(self):
        """Test operation context manager with extra labels."""
        monitor = OperationMonitor('test-service')
        extra_labels = {'user_id': 'user123', 'feature': 'chat'}

        with patch.object(monitor, '_record_metrics') as mock_record:
            with monitor.operation('test-op', extra_labels=extra_labels):
                pass

            args, kwargs = mock_record.call_args
            _, _, _, recorded_extra_labels = args
            assert recorded_extra_labels == extra_labels

    @patch('app.monitoring.OPERATION_LATENCY')
    @patch('app.monitoring.OPERATION_COUNT')
    def test_record_metrics(self, mock_count, mock_latency):
        """Test _record_metrics method."""
        monitor = OperationMonitor('test-service')

        # Mock the labels method
        mock_latency.labels.return_value.observe = lambda x: None
        mock_count.labels.return_value.inc = lambda: None

        monitor._record_metrics('test-op', 1.5, True, {'extra': 'label'})

        # Verify metrics were labeled and called correctly
        mock_latency.labels.assert_called_with(
            service='test-service', operation='test-op', success='true'
        )
        mock_count.labels.assert_called_with(
            service='test-service', operation='test-op', success='true'
        )


class TestClientTracking:
    """Test client tracking functions."""

    @patch('app.monitoring.CLIENT_REQUEST_COUNT')
    @patch('app.monitoring.CLIENT_REQUEST_LATENCY')
    def test_track_client_request(self, mock_latency, mock_count):
        """Test track_client_request function."""
        mock_count.labels.return_value.inc = lambda: None
        mock_latency.labels.return_value.observe = lambda x: None

        track_client_request('s3', 'get_object', 'success', 0.5)

        mock_count.labels.assert_called_with(
            client='s3', operation='get_object', status='success'
        )
        mock_latency.labels.assert_called_with(client='s3', operation='get_object')

    @patch('app.monitoring.CLIENT_ERRORS')
    def test_track_client_error(self, mock_errors):
        """Test track_client_error function."""
        mock_errors.labels.return_value.inc = lambda: None

        track_client_error('s3', 'get_object', 'NoSuchKey')

        mock_errors.labels.assert_called_with(
            client='s3', operation='get_object', error_type='NoSuchKey'
        )

    @patch('app.monitoring.CIRCUIT_BREAKER_STATE')
    def test_set_circuit_breaker_state(self, mock_state):
        """Test set_circuit_breaker_state function."""
        mock_state.labels.return_value.set = lambda x: None

        # Test closed state
        set_circuit_breaker_state('bedrock', True)
        mock_state.labels.assert_called_with(client='bedrock')

        # Test open state
        set_circuit_breaker_state('bedrock', False)
        mock_state.labels.assert_called_with(client='bedrock')


class TestChatTracking:
    """Test chat tracking functions."""

    @patch('app.monitoring.CHAT_MESSAGE_COUNT')
    @patch('app.monitoring.CHAT_TOKEN_COUNT')
    @patch('app.monitoring.LLM_TOKEN_USAGE')
    def test_track_chat_message(
        self, mock_llm_tokens, mock_chat_tokens, mock_chat_count
    ):
        """Test track_chat_message function."""
        mock_chat_count.labels.return_value.inc = lambda: None
        mock_chat_tokens.labels.return_value.inc = lambda x: None
        mock_llm_tokens.labels.return_value.inc = lambda x: None

        track_chat_message('user', 'claude-3-sonnet', 100)

        mock_chat_count.labels.assert_called_with(
            direction='user', model='claude-3-sonnet'
        )
        mock_chat_tokens.labels.assert_called_with(
            direction='user', model='claude-3-sonnet'
        )
        mock_llm_tokens.labels.assert_called_with(
            model='claude-3-sonnet',
            token_type='prompt',  # noqa: S106
        )


class TestModelTracking:
    """Test model tracking functions."""

    @patch('app.monitoring.LLM_REQUEST_COUNT')
    @patch('app.monitoring.CHAT_MESSAGE_COUNT')
    def test_track_model_request(self, mock_chat_count, mock_llm_count):
        """Test track_model_request function."""
        mock_llm_count.labels.return_value.inc = lambda: None
        mock_chat_count.labels.return_value.inc = lambda: None

        track_model_request('claude-3-sonnet', 'success')

        mock_llm_count.labels.assert_called_with(
            model='claude-3-sonnet', status='success'
        )
        mock_chat_count.labels.assert_called_with(
            direction='assistant', model='claude-3-sonnet'
        )

    @patch('app.monitoring.LLM_ERROR_COUNT')
    @patch('app.monitoring.LLM_REQUEST_COUNT')
    def test_track_llm_error(self, mock_request_count, mock_error_count):
        """Test track_llm_error function."""
        mock_error_count.labels.return_value.inc = lambda: None
        mock_request_count.labels.return_value.inc = lambda: None

        track_llm_error('claude-3-sonnet', 'rate_limit')

        mock_error_count.labels.assert_called_with(
            model='claude-3-sonnet', error_type='rate_limit'
        )
        mock_request_count.labels.assert_called_with(
            model='claude-3-sonnet', status='error'
        )

    @patch('app.monitoring.LLM_TOKEN_USAGE')
    @patch('app.monitoring.CHAT_TOKEN_COUNT')
    @patch('app.monitoring.CHAT_LATENCY')
    @patch('app.monitoring.LLM_REQUEST_LATENCY')
    @patch('app.monitoring.track_model_request')
    def test_track_model_usage(
        self,
        mock_track_request,
        mock_llm_latency,
        mock_chat_latency,
        mock_chat_tokens,
        mock_llm_tokens,
    ):
        """Test track_model_usage function."""
        mock_llm_tokens.labels.return_value.inc = lambda x: None
        mock_chat_tokens.labels.return_value.inc = lambda x: None
        mock_chat_latency.labels.return_value.observe = lambda x: None
        mock_llm_latency.labels.return_value.observe = lambda x: None

        usage_data = {'request_tokens': 100, 'response_tokens': 50, 'total_tokens': 150}

        track_model_usage('claude-3-sonnet', usage_data, 2.5)

        # Verify token tracking calls
        assert mock_llm_tokens.labels.call_count == 3  # prompt, completion, total
        assert mock_chat_tokens.labels.call_count == 2  # user, assistant

        # Verify latency tracking
        mock_chat_latency.labels.assert_called_with(model='claude-3-sonnet')
        mock_llm_latency.labels.assert_called_with(model='claude-3-sonnet')

        # Verify model request tracking
        mock_track_request.assert_called_with('claude-3-sonnet', status='success')

    @patch('app.monitoring.LLM_TOKEN_USAGE')
    @patch('app.monitoring.track_model_request')
    def test_track_model_usage_partial_data(self, mock_track_request, mock_llm_tokens):
        """Test track_model_usage with partial usage data."""
        mock_llm_tokens.labels.return_value.inc = lambda x: None

        # Test with only request tokens
        usage_data = {'request_tokens': 100}
        track_model_usage('claude-3-sonnet', usage_data, None)

        # Should only call once for request tokens
        mock_llm_tokens.labels.assert_called_once_with(
            model='claude-3-sonnet',
            token_type='prompt',  # noqa: S106
        )


class TestContextServerTracking:
    """Test context server tracking functions."""

    @patch('app.monitoring.CONTEXT_SERVER_QUERY_COUNT')
    def test_track_context_server_query(self, mock_count):
        """Test track_context_server_query function."""
        mock_count.labels.return_value.inc = lambda: None

        track_context_server_query('opensearch', 'search')

        mock_count.labels.assert_called_with(server='opensearch', operation='search')

    @patch('app.monitoring.CONTEXT_SERVER_LATENCY')
    def test_track_context_server_latency(self, mock_latency):
        """Test track_context_server_latency function."""
        mock_latency.labels.return_value.observe = lambda x: None

        track_context_server_latency('opensearch', 'search', 0.25)

        mock_latency.labels.assert_called_with(server='opensearch', operation='search')

    @patch('app.monitoring.CONTEXT_SERVER_ERROR_COUNT')
    def test_track_context_server_error(self, mock_error_count):
        """Test track_context_server_error function."""
        mock_error_count.labels.return_value.inc = lambda: None

        track_context_server_error('opensearch', 'search', 'timeout')

        mock_error_count.labels.assert_called_with(
            server='opensearch', operation='search', error_type='timeout'
        )
