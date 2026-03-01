"""Tests for attractor.agent.profiles."""

from __future__ import annotations

from unittest.mock import patch

from attractor.agent.execution.local import LocalExecutionEnvironment
from attractor.agent.profiles.anthropic import AnthropicProfile
from attractor.agent.profiles.gemini import GeminiProfile
from attractor.agent.profiles.openai import OpenAIProfile

CORE_TOOLS = {"read_file", "write_file", "edit_file", "shell", "grep", "glob"}


class TestOpenAIProfile:
    def test_has_apply_patch_tool(self):
        profile = OpenAIProfile()
        names = profile.tool_registry.names()
        assert "apply_patch" in names

    def test_registers_core_tools(self):
        profile = OpenAIProfile()
        names = set(profile.tool_registry.names())
        assert CORE_TOOLS.issubset(names)

    def test_model_name(self):
        profile = OpenAIProfile("gpt-4o")
        assert profile.model == "gpt-4o"

    def test_id(self):
        profile = OpenAIProfile()
        assert profile.id == "openai"

    def test_build_system_prompt(self, tmp_path):
        env = LocalExecutionEnvironment(working_dir=str(tmp_path))
        profile = OpenAIProfile()
        with patch("attractor.agent.prompts._find_git_root", return_value=None):
            prompt = profile.build_system_prompt(env)
        assert "apply_patch" in prompt
        assert "coding agent" in prompt


class TestAnthropicProfile:
    def test_registers_core_tools(self):
        profile = AnthropicProfile()
        names = set(profile.tool_registry.names())
        assert CORE_TOOLS.issubset(names)

    def test_build_system_prompt_has_environment(self, tmp_path):
        env = LocalExecutionEnvironment(working_dir=str(tmp_path))
        profile = AnthropicProfile()
        with patch("attractor.agent.prompts._find_git_root", return_value=None):
            prompt = profile.build_system_prompt(env)
        assert "<environment>" in prompt
        assert "Working directory:" in prompt

    def test_id(self):
        profile = AnthropicProfile()
        assert profile.id == "anthropic"

    def test_provider_options_has_beta(self):
        profile = AnthropicProfile()
        opts = profile.provider_options()
        assert opts is not None
        assert "anthropic" in opts


class TestGeminiProfile:
    def test_registers_core_tools(self):
        profile = GeminiProfile()
        names = set(profile.tool_registry.names())
        assert CORE_TOOLS.issubset(names)

    def test_id(self):
        profile = GeminiProfile()
        assert profile.id == "gemini"


class TestAllProfilesRegisterCoreTools:
    def test_all_profiles_have_core_tools(self):
        for profile_cls in (OpenAIProfile, AnthropicProfile, GeminiProfile):
            profile = profile_cls()
            names = set(profile.tool_registry.names())
            missing = CORE_TOOLS - names
            assert not missing, f"{profile_cls.__name__} missing tools: {missing}"
