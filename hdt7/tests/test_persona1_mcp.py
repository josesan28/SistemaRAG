"""Pruebas unitarias del contrato MCP/MAS implementado por Persona 1."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mcp import Client

from hdt7.mcp_server import mcp
from hdt7.multi_agent import (
    FAQ_AGENT_NAME,
    WEATHER_AGENT_NAME,
    _filter_tools_by_agent,
    get_mcp_url,
)


class McpToolFilterTests(unittest.TestCase):
    def _context(self, agent_name: str) -> SimpleNamespace:
        return SimpleNamespace(agent=SimpleNamespace(name=agent_name))

    def test_faq_agent_solo_ve_faq_tool(self) -> None:
        context = self._context(FAQ_AGENT_NAME)
        self.assertTrue(_filter_tools_by_agent(context, SimpleNamespace(name="faq_tool")))
        self.assertFalse(
            _filter_tools_by_agent(context, SimpleNamespace(name="weather_tool"))
        )

    def test_weather_agent_solo_ve_weather_tool(self) -> None:
        context = self._context(WEATHER_AGENT_NAME)
        self.assertTrue(
            _filter_tools_by_agent(context, SimpleNamespace(name="weather_tool"))
        )
        self.assertFalse(_filter_tools_by_agent(context, SimpleNamespace(name="faq_tool")))

    def test_manager_no_recibe_tools_mcp(self) -> None:
        context = self._context("Manager Parachute S.A.")
        self.assertFalse(_filter_tools_by_agent(context, SimpleNamespace(name="faq_tool")))


class McpConfigurationTests(unittest.TestCase):
    def test_url_por_defecto(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_mcp_url(), "http://127.0.0.1:8000/mcp")

    def test_url_configurable(self) -> None:
        with patch.dict(os.environ, {"MCP_SERVER_URL": "http://mcp:9000/mcp"}):
            self.assertEqual(get_mcp_url(), "http://mcp:9000/mcp")


class McpServerContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_servidor_publica_ambas_tools(self) -> None:
        async with Client(mcp) as client:
            tools_result = await client.list_tools()

        self.assertEqual(
            {tool.name for tool in tools_result.tools}, {"faq_tool", "weather_tool"}
        )

    async def test_tools_se_pueden_invocar_via_mcp(self) -> None:
        async with Client(mcp) as client:
            faq = await client.call_tool("faq_tool", {"query": "peso maximo"})
            weather = await client.call_tool(
                "weather_tool", {"fecha": "fecha-invalida"}
            )

        self.assertTrue(faq.structured_content["valido"])
        self.assertFalse(weather.structured_content["valido"])


if __name__ == "__main__":
    unittest.main()

