"""Minimal OPC UA server bridge for the digital twin simulation."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Dict

from asyncua import Node, Server

from src.simulation.environment import SimulationState


@dataclass
class OpcUaConfig:
    endpoint: str = "opc.tcp://0.0.0.0:4840/flow-optimization"
    namespace: str = "HSY.Flow"


class DigitalTwinOpcUaServer:
    """Expose simulation state to external OPC UA clients."""

    def __init__(self, config: OpcUaConfig | None = None) -> None:
        self.config = config or OpcUaConfig()
        self._server = Server()
        self._nodes: Dict[str, Node] = {}
        self._idx: int | None = None
        self._running = False

    async def setup(self) -> None:
        await self._server.init()
        self._server.set_endpoint(self.config.endpoint)
        self._idx = await self._server.register_namespace(self.config.namespace)
        objects = self._server.nodes.objects
        tunnel = await objects.add_object(self._idx, "TunnelState")
        self._nodes["level"] = await tunnel.add_variable(self._idx, "LevelMeters", 0.0)
        self._nodes["volume"] = await tunnel.add_variable(self._idx, "VolumeM3", 0.0)
        self._nodes["inflow"] = await tunnel.add_variable(self._idx, "InflowM3PerHour", 0.0)
        self._nodes["outflow"] = await tunnel.add_variable(self._idx, "OutflowM3PerHour", 0.0)
        self._nodes["price"] = await tunnel.add_variable(self._idx, "PriceEURPerKWh", 0.0)
        for pump in range(1, 9):
            name = f"Pump{pump:02d}Flow"
            self._nodes[name] = await tunnel.add_variable(self._idx, name, 0.0)
        for node in self._nodes.values():
            await node.set_writable()

    async def start(self) -> None:
        if self._running:
            return
        if self._idx is None:
            await self.setup()
        await self._server.start()
        self._running = True

    async def stop(self) -> None:
        if not self._running:
            return
        await self._server.stop()
        self._running = False

    async def update(self, state: SimulationState, info: Dict[str, float]) -> None:
        if not self._running:
            return
        await self._nodes["level"].write_value(state.tunnel_level_m)
        await self._nodes["volume"].write_value(state.tunnel_volume_m3)
        await self._nodes["inflow"].write_value(state.inflow_m3_per_h)
        await self._nodes["outflow"].write_value(info.get("total_outflow", 0.0))
        await self._nodes["price"].write_value(info.get("price", 0.0))
        for idx, pump in enumerate(state.pump_flows_m3_per_h.values(), start=1):
            node = self._nodes.get(f"Pump{idx:02d}Flow")
            if node is not None:
                await node.write_value(float(pump))

    async def __aenter__(self) -> "DigitalTwinOpcUaServer":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()


@asynccontextmanager
async def opcua_server(config: OpcUaConfig | None = None):
    server = DigitalTwinOpcUaServer(config)
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


async def demo_server() -> None:
    server = DigitalTwinOpcUaServer()
    async with server:
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(demo_server())
