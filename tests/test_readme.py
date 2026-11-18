"""
Tests that README.md matches the server.

The README is this project's only user documentation: the docs/ guides were
removed when the README was rewritten (commit ed858c7), and with them the
tests that checked those guides. These tests keep the README honest instead.
Its feature lists are what a user reads to learn what the server offers, so
each list must name exactly what the server registers, and the setup command
it tells users to run must exist.
"""

import re
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP

from zoho_mcp.prompts import register_prompts
from zoho_mcp.resources import register_resources
from zoho_mcp.server import register_tools
from zoho_mcp.transport import setup_argparser

README = (Path(__file__).parent.parent / "README.md").read_text()


def _section(heading: str) -> str:
    """Return the text under a '### heading' up to the next heading."""
    match = re.search(rf"^### {heading}\n(.*?)(?=^#)", README, re.M | re.S)
    assert match, f"README has no '### {heading}' section"
    return match.group(1)


@pytest.fixture
def server():
    mcp = FastMCP(name="readme")
    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
    return mcp


@pytest.mark.asyncio
async def test_readme_lists_every_tool(server):
    """The Tools section names exactly the registered tools."""
    listed = set()
    for line in _section("Tools").splitlines():
        if line.startswith("**"):
            listed.update(name.strip() for name in line.split(":", 1)[1].split(","))
    registered = {t.name for t in await server.list_tools()}
    assert listed == registered


@pytest.mark.asyncio
async def test_readme_lists_every_resource(server):
    """The Resources section names exactly the registered resources."""
    listed = set(re.findall(r"\*\*(\w+://[\w{}/]+)\*\*", _section("Resources")))
    # Templated resources (contact://{contact_id}) are listed apart from
    # static ones, so both lists count.
    registered = {str(r.uri) for r in await server.list_resources()} | {
        t.uriTemplate for t in await server.list_resource_templates()
    }
    assert listed == registered


@pytest.mark.asyncio
async def test_readme_lists_every_prompt(server):
    """The Prompts section names exactly the registered prompts."""
    listed = set(re.findall(r"\*\*(\w+)\*\*", _section("Prompts")))
    registered = {p.name for p in await server.list_prompts()}
    assert listed == registered


def test_readme_setup_oauth_command_exists():
    """The README's refresh-token command is a real command-line option."""
    assert "uvx zoho-books-mcp --setup-oauth" in README
    args = setup_argparser().parse_args(["--setup-oauth"])
    assert args.setup_oauth is True


def test_readme_has_troubleshooting():
    """The README keeps the troubleshooting notes the removed guide held."""
    assert "### Troubleshooting" in README
    assert "--setup-oauth" in _section("Troubleshooting")
