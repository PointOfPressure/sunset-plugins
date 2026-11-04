# Sunset plugin API (version 2)

For [Sunset](https://github.com/PointOfPressure/sunset-client) 0.9 on Horizon `ba6344a`. Everything in this repo is
MIT: copy it, change it, ship your plugin under whatever licence you like.

A Sunset plugin is a small Rust file that adds modules, commands and event handlers to Sunset: anything a built-in
module does (settings in the click GUI, key binds, ticks, packets, HUD and world drawing, friends, saved data) goes
through one module Sunset provides, `sunset_api`. It is a [Horizon native mod](https://github.com/horizon-rust/horizon/blob/main/docs/native-mods.md)
built into the game together with Sunset.

Examples: [`examples/hello-plugin`](examples/hello-plugin) (a module with settings, a command, HUD and world drawing, a
packet handler, timers, saved data) and [`examples/afk-plugin`](examples/afk-plugin) (AFK Fisher: unattended fishing
that logs out on danger and survives reconnects). What changed: [CHANGELOG.md](CHANGELOG.md).

## Quick start

```sh
python3 tools/new.py autowave "Auto Wave"     # makes plugins/autowave/ from the template
# edit plugins/autowave/mixins/autowave/plugin.rs
python3 tools/build.py plugins/autowave       # packs it, installs it next to Sunset, builds the game
```

`build.py` needs Sunset installed (its install script) and the Horizon launcher (`horizon-launcher` on the PATH, or
`HORIZON_LAUNCHER=/path/to/horizon-launcher`). Without the launcher it installs the plugin and tells you to press
Settings > Game > Native mods > Build. In the game, `.plugins` lists your plugin and `.help` its command.

## What a plugin is

A folder with four files:

```
autowave/
  horizon-native.json          id, version, Horizon commit (same as Sunset's)
  mixins/autowave/
    horizon-mixin.toml         adds plugin.rs to the game and hooks the game's tick to tick.rs
    tick.rs                    one line that calls your plugin (leave it as it is)
    plugin.rs                  your code
```

The id (here `autowave`) must be the same in all of them: `tools/new.py` does that for you. Both manifests name the
Horizon commit Sunset is built for (`ba6344a59cb9e755b730dcf02285fc0d33b97d3c` for Sunset 0.9).

## The template

`template/mixins/myplugin/plugin.rs`, the whole of a working plugin:

```rust
use super::Game;
use super::sunset_api as api;

// A Sunset older than plugin API 2 stops the build here with "update Sunset".
const _: () = api::needs(2);

const ID: &str = "myplugin";
const NAME: &str = "My Module";

// Called every tick; the first call runs `setup`.
pub(super) fn tick(game: &mut Game<'_>) {
    api::plugin(game, ID, "0.1.0", setup);
}

fn setup(p: &mut api::Plugin) {
    // Your module in the click GUI, with its settings.
    p.module(
        api::Module::new(NAME, api::Category::Player, "What my module does.")
            .bool("Tell me", true)
            .num("Every (seconds)", 5.0, 1.0, 60.0, 1.0),
    );

    // Runs every tick while you are in a world.
    p.on_tick(|game| {
        // None while the module is off.
        let Some(m) = api::module(NAME) else {
            return;
        };
        if m.b("Tell me") && game.ticks % (m.n("Every (seconds)") as u64 * 20) == 0 {
            if let Some(me) = api::me(game) {
                api::chat(game, &format!("{NAME}: {:.0} health", me.health));
            }
        }
    });

    // A chat command: .mycommand
    p.command("mycommand", "what .mycommand does", |game, args| {
        api::chat(game, &format!("{NAME} got {} arguments", args.len()));
    });
}
```

Everything below goes inside `setup` (the `p.` calls) or inside a handler (the `api::` calls). Handlers are closures;
Rust works out their argument types from the call, so write them as in the snippets.

## Reference

Ticks are 20 a second. Positions are `[x, y, z]` (`f64` for places, `i32` for blocks). Colours are `0xAARRGGBB`
(`0xFF` alpha is opaque); text colours `0xRRGGBB`. Item and block ids are written without `minecraft:` (`"cod"`,
`"oak_log"`); where a call takes an id, a comma list works too (`"cod,salmon"`).

### Plugin and version

| Call | What it does |
| --- | --- |
| `api::API_VERSION` | `2`. A new version only adds things: plugins made for 1 or 2 keep working. |
| `const _: () = api::needs(2);` | Put at the top of plugin.rs: on an older Sunset the build stops with "update Sunset". |
| `api::plugin(game, id, version, setup)` | Registers your plugin the first time (runs `setup`); later calls do nothing. Call it from `tick`. `id`: your mod's id. |
| `p.id()` | Your plugin's id, inside `setup`. |

### Modules and settings

```rust
p.module(
    api::Module::new("Auto Wave", api::Category::Player, "Waves at players.")
        .bool("Only friends", false)                       // a switch
        .num("Range", 8.0, 1.0, 32.0, 0.5)                 // default, min, max, step
        .pick("Hand", &["Main", "Off"])                    // a choice; the first is the default
        .text("Message", "o/"),                            // text, or a comma list
);
```

`Category` is one of `Combat`, `Movement`, `Player`, `Render`, `World`, `Client`. Your module gets everything a
built-in one has: the click GUI (left click on/off, right click settings), `.t`, `.set`, `.settings`, `.bind` (key
binds, Toggle or Hold), `.reset`, profiles, and its settings and state saved in Sunset's config. A name Sunset (or
another plugin) already has is refused with a chat line.

| Call | Snippet |
| --- | --- |
| `api::module(name)` | The module's settings while it is **on**, else `None`: `let Some(m) = api::module("Auto Wave") else { return };` |
| `m.b(setting)`, `m.n(..)`, `m.p(..)`, `m.t(..)` | Read a switch (`bool`), number (`f64`), choice (`&str`) or text (`&str`): `let range = m.n("Range");` |
| `api::find_module(name)` | Any module (Sunset's too), on or off: `let ka = api::find_module("Kill Aura").map(\|m\| m.n("Range"));` |
| `api::is_on(name)` | `if api::is_on("Kill Aura") { ... }` |
| `api::modules()` | Every module with its settings: `for m in api::modules() { if m.on { api::chat(game, m.name); } }` |
| `api::toggle(game, name, on)` | Turns a module on or off (nothing if it already is): `api::toggle(game, "Auto Fish", true)?;` or `let _ = api::toggle(..);` |
| `api::set(game, module, setting, value)` | Changes any module's setting; `value`: `bool`, a number or text. Ok: the setting as shown (`"Range: 4.5"`). `if let Err(e) = api::set(game, "Kill Aura", "Range", 4.5) { api::chat(game, &e); }` |
| `api::register(module)`, `api::turn_off(game, name)` | Version 1's calls (`register` adds a module outside `setup`); still work. |

Names are found as `.t` finds them: case and spaces don't matter. Errors say what exists:
`Kill Aura has no setting "Rnge". Its settings: Range, ...`, `"far" is not a value for Kill Aura > Range: give a
number from 1 to 6.`, `No module called "Kil Aura". Did you mean Kill Aura?`.

### Commands

```rust
p.command("wave", "wave at someone: .wave <name>", |game, args| {
    let Some(name) = args.first() else {
        api::chat(game, "Use .wave <name>");
        return;
    };
    let _ = api::say_server(game, &format!("o/ {name}"));
});
```

`.wave Steve` runs it with `args = ["Steve"]`. The second text is the line `.help` shows. Sunset's own command names
(`set`, `t`, `friend`...) and names with spaces are refused with a chat line.

### Events

Each `p.on_...` adds a handler; Sunset calls it for as long as the game runs (check `api::module(..)` inside to do
something only while your module is on). Handlers of one event run highest priority first: `p.priority(api::HIGH)`
applies to the handlers added after it (`HIGHEST` 200, `HIGH` 100, `NORMAL` 0, the default, `LOW` -100, `LOWEST`
-200; any `i32`).

| Handler | When | Snippet |
| --- | --- | --- |
| `on_tick(\|game\| ..)` | Each tick in a world, where Sunset's modules run (after the tick's move packet). | `p.on_tick(\|game\| { if let Some(me) = api::me(game) { /* ... */ } });` |
| `on_pre_tick(\|game\| ..)` | Each tick before the game moves you: set keys or the look here. | `p.on_pre_tick(\|game\| { /* game.keys ... */ });` |
| `on_enable(name, \|game\| ..)` | The module turned on (or was on when the game started). | `p.on_enable("Auto Wave", \|game\| api::chat(game, "on"));` |
| `on_disable(name, \|game\| ..)` | The module turned off (GUI, bind, `.t`, Panic, another plugin...). | `p.on_disable("Auto Wave", \|game\| api::chat(game, "off"));` |
| `on_toggle(\|game, name, on\| ..)` | Any module turned on or off. | `p.on_toggle(\|game, name, on\| if name == "Kill Aura" && on { /* ... */ });` |
| `on_packet_out(\|game, packet\| ..)` | Every packet you send, before it goes: read it, `packet.cancel()`, or `packet.replace(other)`. | `p.on_packet_out(\|_game, packet\| if matches!(packet.packet(), api::packets::Serverbound::Attack(_)) { packet.cancel(); });` |
| `on_packet_in(\|game, packet\| ..)` | Every packet the server sent, at the next tick, after the game handled it (read only). | `p.on_packet_in(\|game, packet\| if let api::packets::Clientbound::SetTime(_) = packet { /* ... */ });` |
| `on_key(\|game, key, down\| ..)` | A key or mouse button went down (`true`) or up: `"key.keyboard.h"`, `"key.mouse.left"`. | `p.on_key(\|game, key, down\| if down && key == "key.keyboard.h" { api::chat(game, "H!"); });` |
| `on_hud(\|game, draw\| ..)` | Each frame, over the HUD (GUI pixels). | `p.on_hud(\|_game, draw\| draw.label("Hi", [4.0, 60.0], 0xFFFFFF));` |
| `on_world(\|game, draw\| ..)` | Each frame in a world: boxes and labels at places. | `p.on_world(\|_game, draw\| { draw.block([0, 64, 0], 0xFF40A0FF); });` |
| `on_chat(\|game, line\| ..)` | A chat line from the server or a player (`line.text`, `line.player`). Sunset's own lines are left out. | `p.on_chat(\|game, line\| if line.text.contains("restart") { /* ... */ });` |
| `on_hurt(\|game, h\| ..)` | Your health went down since the last tick: `h.health`, `h.before`. | `p.on_hurt(\|game, h\| api::chat(game, &format!("-{:.0}", h.before - h.health)));` |
| `on_low_health(below, \|game, h\| ..)` | Your health went under `below` (again each time it went back up first). | `p.on_low_health(8.0, \|game, _h\| api::stop_everything(game, "low health"));` |
| `on_death(\|game\| ..)` | You died (the death screen came up). | `p.on_death(\|game\| api::chat(game, "died"));` |
| `on_join(\|game\| ..)` | The first tick in a world after joining a server or opening a world (reconnects too; not respawns). | `p.on_join(\|game\| api::chat(game, "joined"));` |
| `on_disconnect(\|game, d\| ..)` | The connection ended: `d.reason`, `d.by_server` (a kick or shutdown), `d.retry` (Horizon's Auto-reconnect will try again). | `p.on_disconnect(\|_game, d\| eprintln!("left: {}", d.reason));` |
| `on_stop(\|game, why\| ..)` | Everything was stopped (`api::stop_everything` or Panic): let go of what you hold. | `p.on_stop(\|_game, _why\| { /* reset your state */ });` |

Packets: `packet.packet()` is the packet, `packet.is_move()` whether it is the tick's move packet, `packet.cancel()`
keeps it from going (handlers of lower priority don't see it), `packet.replace(p)` sends `p` instead. A move packet
can only become another move packet, and nothing else can become one (one move packet a tick): such a change is
refused with a chat line. The packet types are Horizon's (`api::packets::Serverbound::...`,
`api::packets::Clientbound::...`, in its `horizon-protocol` crate).

Incoming packets can't be cancelled (the game has no place to stop them before it handles them); a handler sees
them a tick later.

If a handler, command or task panics, your plugin is switched off (all its handlers, commands and tasks) and chat
says where; `.plugins` shows why. The game goes on.

### Drawing

The `draw` in `on_hud` and `on_world`:

| Call | Snippet |
| --- | --- |
| `draw.size()` | `[width, height]` in GUI pixels: `let [w, _h] = draw.size();` |
| `draw.rect([x, y, w, h], argb)` | `draw.rect([2.0, 60.0, 80.0, 12.0], 0x80000000);` |
| `draw.label(text, [x, y], rgb)` | `draw.label("AFK", [4.0, 62.0], 0xFFD27F);` |
| `draw.line([x, y], [x, y], argb)` | `draw.line([0.0, 0.0], [50.0, 50.0], 0xFFFF0000);` |
| `api::text_width(game, text)` | Width of a line in pixels: `draw.rect([2.0, 60.0, api::text_width(game, &t) + 4.0, 12.0], 0x80000000);` |
| `draw.block(pos, argb)` | World only: a box round a block (false when out of sight): `draw.block([x, y, z], 0xFFFFA040);` |
| `draw.cuboid(lo, hi, argb)` | World only: a box between two corners: `draw.cuboid([0.0, 64.0, 0.0], [1.0, 66.0, 1.0], 0xFF40FF40);` |
| `draw.tag(at, text, rgb)` | World only: text at a place: `draw.tag([0.5, 66.0, 0.5], "here", 0xFFFFFF);` |
| `draw.project(at)` | World only: where a place is on screen, `None` behind you: `if let Some([x, y]) = draw.project(p) { ... }` |

Sunset hides all of it while the F1 HUD is off or after `.panic`.

### You, the world, items, entities

| Call | Snippet |
| --- | --- |
| `api::me(game)` | `Some(Me)` in a world: `pos`, `eye`, `velocity`, `yaw`, `pitch` (degrees), `health`, `absorption`, `food`, `on_ground`, `dimension` (`"minecraft:overworld"`), `slot` (hotbar 0 to 8), `dead`. `if let Some(me) = api::me(game) { let y = me.pos[1]; }` |
| `api::in_world(game)` | In a world with no menu or death screen up: `if !api::in_world(game) { return; }` |
| `api::block(game, pos)` | The block id there: `if api::block(game, [x, y - 1, z]) == "water" { ... }` |
| `api::entities(game)` | Every living thing but you, nearest first: `id`, `kind` (`"minecraft:zombie"`), `name`, `pos`, `health`, `player`, `friend`, `distance`. `let near = api::entities(game).into_iter().find(\|e\| e.kind == "minecraft:creeper" && e.distance < 6.0);` |
| `api::players(game)` | The other players, nearest first (friends included: check `friend`): `for p in api::players(game) { if !p.friend && p.distance < 20.0 { ... } }` |
| `api::item(game, slot)` | `Some(Item { id, count, damage })` in a slot (0 to 8 hotbar, 9 to 35 inventory, 40 off hand): `let rod = api::item(game, 0).is_some_and(\|i\| i.id == "fishing_rod");` |
| `api::count(game, id)` | How many you carry: `let fish = api::count(game, "cod,salmon");` |
| `api::find_item(game, id)` | First slot holding it, hotbar first: `if let Some(slot) = api::find_item(game, "golden_apple") { ... }` |
| `api::combat_target()` | Who Kill Aura is hitting while on: `if let Some(id) = api::combat_target() { ... }` |
| `game` | Everything else of the game is reachable too (`game.inventory`, `game.player`, `game.mobs`...): those are Horizon's internals and can change between Horizon versions; the `api::` calls are kept working. |

### Doing things (through Sunset's safe paths)

| Call | Snippet |
| --- | --- |
| `api::chat(game, text)` | A `[Sunset]` line only you see: `api::chat(game, "done");` |
| `api::say_server(game, text)` | A chat message or `/command` to the server (256 characters at most): `let _ = api::say_server(game, "/home");` |
| `api::hold(game, slot)` | Holds a hotbar slot (sent once): `api::hold(game, 2);` |
| `api::use_item(game)` | A right click with what you hold (eat, cast, throw, place): `let _ = api::use_item(game);` |
| `api::attack(game, id)` | Hits an entity as Kill Aura does (Criticals ride along): `api::attack(game, e.id);` |
| `api::turn(who, yaw, pitch)` | The server sees you look there on the tick's own move packet (your screen doesn't turn): `api::turn("Auto Wave", 90.0, 0.0);` |
| `api::turn_then(who, yaw, pitch, \|game\| ..)` | Look there, then act once the server has the look: `api::turn_then("Auto Wave", yaw, pitch, \|game\| api::attack(game, id));` |
| `api::look_at(eye, point)` | `(yaw, pitch)` from your eye to a point: `let (yaw, pitch) = api::look_at(me.eye, target);` |
| `api::place_block(game, pos, slot, rotate, check_entities)` | Places a block from a hotbar slot as Sunset's modules do: `api::place_block(game, [x, y, z], slot, true, true);` |
| `api::send(game, packet)` | Any other packet. Move packets and held-slot changes are refused (use `turn`/`hold`): `api::send(game, api::packets::Serverbound::ClientCommand(..))?;` |
| `api::sequence(game)` | The game's own sequence number, for block actions you send yourself (never keep your own). |
| `api::player_target(game, range, priority)` | Kill Aura's pick: `api::player_target(game, 6.0, "Lowest distance")` (`api::PRIORITIES` lists them). |

Also there from version 1: `can_place`, `replaceable`, `is_air`, `facts`, `find_hotbar`, `find_inventory`, `in_reach`,
`clear_line`, `listed`, `other_players`, `every_living`, `show(pos, argb)`, `dist`, `center_of`, `short`, `turned_to`,
`Camera`, `Canvas`, `Shape`, `line`, `outline`.

### Friends

| Call | Snippet |
| --- | --- |
| `api::friends()` | `let names = api::friends();` |
| `api::is_friend(name)` | `if api::is_friend("Steve") { ... }` |
| `api::add_friend(game, name)` / `api::remove_friend(game, name)` | Saved with Sunset's config; Kill Aura and the rest leave friends alone: `api::add_friend(game, "Steve");` |

### Timers

| Call | Snippet |
| --- | --- |
| `api::after(ticks, \|game\| ..)` | Once, `ticks` from now; returns an id: `api::after(40, \|game\| api::chat(game, "2 s later"));` |
| `api::every(ticks, \|game\| ..)` | Again and again: `let id = api::every(20, \|game\| { /* once a second */ });` |
| `api::cancel(id)` | Stops one (also from inside it): `api::cancel(id);` |
| `api::tasks()` | How many are waiting. |

Ticks count only in a world: a timer waits while you are disconnected and goes on after you are back.
`stop_everything` and Panic drop every timer.

### Saved data

| Call | Snippet |
| --- | --- |
| `api::save(game, ID, key, value)` | Keeps text under a key for your plugin, across restarts: `api::save(game, ID, "count", &n.to_string())?;` |
| `api::load(game, ID, key)` | `let n: u64 = api::load(game, ID, "count").and_then(\|t\| t.parse().ok()).unwrap_or(0);` |

One file per key in `horizon-mods/.horizon-mod-data/<your id>/`; an unchanged value isn't written again. Keys: letters,
digits, `-`, `_` and `.`. Your module's settings are saved by Sunset already: use this for anything else. Plain
`static` values in your plugin outlast disconnects and reconnects (they go when the game closes).

### Unattended play (AFK)

| Call | Snippet |
| --- | --- |
| `api::stop_everything(game, why)` | The safe stop: every module off, held keys let go, every timer dropped, every plugin's `on_stop` run, a chat line: `api::stop_everything(game, "a player came near");` |
| `api::disconnect(game)` | Leaves the server (or closes single player) before the next frame, on purpose: Auto-reconnect doesn't retry it. |
| `api::auto_reconnect(game, on)` | Horizon's own Auto-reconnect for this session: retries a lost connection or a server restart (five tries, 5 to 60 s apart), never a kick or ban: `api::auto_reconnect(game, true);` |
| `api::auto_reconnect_on(game)` | Whether it is on. |

With those and the events (`on_hurt`/`on_low_health`, `on_death`, `on_disconnect` with `retry`, `on_join`,
`on_chat`, `on_stop`) and timers, a plugin can run for hours alone. A pattern, from AFK Fisher:

```rust
fn danger(game: &mut Game<'_>, why: &str) {
    api::stop_everything(game, &format!("AFK: {why}"));   // nothing keeps acting
    api::disconnect(game);                                 // and off the server
}
// in setup:
p.on_low_health(10.0, |game, _h| danger(game, "low health"));
p.on_death(|game| danger(game, "died"));
p.on_join(|game| if api::is_on("My AFK") { api::chat(game, "back in after a reconnect"); });
```

## Rules that keep a server from kicking you

- **One move packet a tick.** The game sends one; a second gets you kicked on Horizon's and vanilla servers. Turn the
  look the server sees with `turn`/`turn_then`, change the tick's own packet in `on_packet_out`; `api::send` refuses
  move packets.
- **Block actions use the game's sequence number** (`api::sequence`), never a counter of your own.
- **Change the held slot once** (`api::hold`); a second change in a row flags anticheats.
- Don't hook a game function that uses a macro (`vec!`, `format!`, `log::`...) in your own `horizon-mixin.toml`: the
  mixin tool refuses it. The one tick hook the template has is all a plugin needs.
- Nothing that hides Sunset (from the mod list, from servers): such plugins are not welcome here.

## When it doesn't work

| You see | Do this |
| --- | --- |
| `this plugin needs a newer Sunset plugin API...` while building | Update Sunset (its install script), then build again. |
| `made for different Horizon revisions` | Set `horizon_revision` (horizon-mixin.toml) and `horizon` (horizon-native.json) to the commit in Sunset's `horizon-native.json`. |
| `cannot find function ... in module api` | Check the name in this page; `api::` calls need `use super::sunset_api as api;`. |
| `expected closure that takes 2 arguments` | The handler takes the arguments its row above shows: `\|game, args\|` for a command, `\|game\|` for a tick. |
| `type ... is more private than the item` | Write `pub(super) fn tick`, not `pub(crate)` or `pub`. |
| Chat: `Plugin x: a module called ... is already there` | Give your module another name. |
| Chat: `the command .x can't be added` | Pick another command name (letters, digits, `-`, `_`; not one of Sunset's). |
| Chat: `Plugin x is off: its tick code panicked: ...` | Your code panicked (an `unwrap()` on `None`, an index past the end...); the text says where. Fix it and build again. |
| `.plugins` doesn't list it | The plugin isn't built in: `mod.<id>: true` in horizon-mods.txt and a build after installing (`tools/build.py` does both). |

## For AI assistants writing a plugin

Write only `plugin.rs` (start from the template above, keep its first lines and `tick`), use only `api::` calls from
this page, write handlers as closures exactly as the snippets do (the arguments are `game` first), return early with
`let Some(m) = api::module(NAME) else { return; };` to act only while the module is on, keep state in a
`static X: std::sync::Mutex<...>` (handlers must be `Send`), use `format!` for text, and never send move packets.
Everything else in the folder comes from `tools/new.py`.

## Building without the launcher

To check that a plugin compiles, stage it with Sunset using [horizon-mixins](https://github.com/horizon-rust/horizon-mixins)
on Horizon's source at the pinned commit and run `cargo check -p horizon-client`. `python3 tools/pack.py <folder>` only
packs `dist/<id>-<version>.hnmod`.
