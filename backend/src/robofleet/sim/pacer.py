"""Wall-clock simulation pacing layer (Phase 2).
Executes simulation steps in an asyncio task with configurable speed multiplier,
pause/resume, and single-step controls. Lives strictly outside the core engine.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress

from robofleet.contracts.events import Event
from robofleet.contracts.state import DynamicState
from robofleet.sim.engine import SimEngine


class SimulationPacer:
    """Async pacing wrapper around SimEngine."""

    def __init__(
        self,
        engine: SimEngine,
        speed_multiplier: float = 1.0,
        start_paused: bool = False,
    ) -> None:
        self.engine = engine
        self._speed_multiplier = max(0.1, min(20.0, speed_multiplier))
        self._is_paused = start_paused
        self._is_running = False
        self._step_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._callbacks: list[Callable[[DynamicState, list[Event]], Awaitable[None]]] = []

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def speed_multiplier(self) -> float:
        return self._speed_multiplier

    def register_callback(
        self, callback: Callable[[DynamicState, list[Event]], Awaitable[None]]
    ) -> None:
        self._callbacks.append(callback)

    def set_speed(self, multiplier: float) -> None:
        """Set simulation speed multiplier (0.5x to 20x)."""
        self._speed_multiplier = max(0.1, min(20.0, float(multiplier)))

    def pause(self) -> None:
        """Pause the simulation."""
        self._is_paused = True

    def resume(self) -> None:
        """Resume the simulation."""
        self._is_paused = False
        self._step_event.set()

    def step_once(self) -> None:
        """Trigger exactly one simulation tick while paused."""
        if self._is_paused:
            self._step_event.set()

    async def restart(self) -> None:
        """Atomically resets the engine and broadcasts fresh snapshot."""
        async with self._lock:
            self.engine.reset()
            self._step_event.clear()
            recent_events = list(self.engine.events)
            self.engine.events.clear()
            dynamic_state = self.engine.get_dynamic_state()

        for cb in self._callbacks:
            with suppress(Exception):
                await cb(dynamic_state, recent_events)

    def stop(self) -> None:
        """Stop the pacing task loop."""
        self._is_running = False
        self._step_event.set()

    async def run(self) -> None:
        """Main async pacing loop."""
        self._is_running = True
        tick_hz = self.engine.config.timing.tick_hz
        base_dt = 1.0 / tick_hz

        while self._is_running:
            if self._is_paused:
                # Wait until resumed or single step requested
                await self._step_event.wait()
                self._step_event.clear()
                if not self._is_running:
                    break

            # Execute simulation step
            async with self._lock:
                self.engine.step()
                recent_events = list(self.engine.events)
                self.engine.events.clear()
                dynamic_state = self.engine.get_dynamic_state()

            # Broadcast to registered callbacks (e.g. WebSocket managers)
            for cb in self._callbacks:
                with suppress(Exception):
                    await cb(dynamic_state, recent_events)

            # Calculate sleep duration based on speed multiplier
            sleep_time = base_dt / self._speed_multiplier
            await asyncio.sleep(sleep_time)
