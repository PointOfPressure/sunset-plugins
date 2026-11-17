# Changelog

## Plugin API 3 (pending Sunset Baritone integration)

- Template and both examples target Horizon `9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0`, horizon-mixins
  `e59da9094f0c2fdda6c627fe9eff22dec6a906f0`, and require plugin API 3 at compile time.
- Document the optional Baritone provider table, registration rules and its separate version 1 service protocol.
  Existing API 1 and 2 calls remain available.
- Document `running()` and permanent Panic cleanup, plus the reserved `seed`, `baritone` and `b` commands.
- API 3 currently requires Sunset's `pr37-port` integration; main at `1e4fb18` still exposes API 2.
- `build.py` explicitly builds the instance it installed into and passes the same game-data root to the launcher,
  so a different selected instance no longer redirects the build.

## Plugin API 2 (Sunset 0.9)

- `api::plugin(game, id, version, setup)`: a plugin registers once and adds its modules, commands and handlers in
  `setup`; `const _: () = api::needs(2);` stops the build on an older Sunset with "update Sunset".
- Events with priorities (`p.priority(..)`): tick, pre tick, enable/disable/toggle (any module, any way it was
  switched), packets out (cancel, replace; one move packet a tick kept), packets in (read only), keys, HUD and world
  drawing (`Draw`: rect, label, line, block, cuboid, tag, project), chat, hurt, low health, death, join, disconnect
  (reason, by the server, retried), stop. A handler that panics switches its plugin off with a chat line; the game
  goes on.
- Any module: `find_module`, `is_on`, `modules`, `set` (typed, with errors that list what exists), `toggle`.
- Reads: `me`, `in_world`, `block`, `entities`, `players`, `item`, `count`, `find_item`, `combat_target`.
- Actions: `send` (move packets and slot changes refused, with the fix), `say_server`, `use_item`, `attack`,
  `text_width`.
- Friends: `friends`, `is_friend`, `add_friend`, `remove_friend`.
- Timers: `after`, `every`, `cancel`, `tasks` (in-world ticks: they wait out a reconnect).
- Saved data: `save`, `load` (a file per key in the plugin's data folder).
- AFK: `stop_everything`, `disconnect`, `auto_reconnect`, `auto_reconnect_on`.
- Sunset: `.plugins` lists the plugins (version, modules, commands, why one is off); `.help` lists their commands;
  `.reset` and a slider's right click on a plugin's module no longer crash the game.
- This repo: the full reference with a snippet per call, `template/`, `tools/new.py` (a new plugin from the
  template), `tools/build.py` (pack, install and build in one command), the hello example on version 2, and a new
  example, AFK Fisher (`examples/afk-plugin`).

Version 1's calls (`register`, `module`, `chat`, `turn_off` and the helpers) work as they did.

## Plugin API 1 (Sunset 0.8.1)

- `register`, `module`, `chat`, `turn_off`, `Module` settings and Sunset's placing and targeting helpers.
