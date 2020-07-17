import pytest
from unittest import mock
import sys

import tests._mock_weechat as mock_weechat

sys.modules['weechat'] = mock_weechat

import wee_matter
import tests._mock_config as mock_config

@mock.patch('wee_matter.config', return_value=mock_config)
def test_build_post_from_input_data(mock_config):
    wee_matter.server.load_server("basic")

    builded_post = wee_matter.post.build_post_from_input_data("basic", "a banal message")

    assert "a banal message" == builded_post.message
