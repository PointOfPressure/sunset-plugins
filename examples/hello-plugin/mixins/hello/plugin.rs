// Hello, an example Sunset plugin (plugin API 2): a module with settings, a chat command, a HUD line, a box in the
// world, a packet handler, enable/disable handlers, a timer and a value kept across restarts.

use super::Game;
use super::sunset_api as api;

// Stops the build with "update Sunset" on a Sunset older than plugin API 2.
const _: () = api::needs(2);

const ID: &str = "hello";

// Called by tick.rs every tick: the first call runs setup, later ones do nothing.
pub(super) fn tick(game: &mut Game<'_>) {
    api::plugin(game, ID, "0.2.0", setup);
}

// What the handlers below count, for `.hello stats`.
static STATS: std::sync::Mutex<[u64; 4]> = std::sync::Mutex::new([0; 4]);
const HUD: usize = 0;
const WORLD: usize = 1;
const BLOCKED: usize = 2;
const SAID: usize = 3;

fn count(what: usize) {
    STATS.lock().unwrap_or_else(|e| e.into_inner())[what] += 1;
}

fn setup(p: &mut api::Plugin) {
    p.module(
        api::Module::new("Hello", api::Category::Player, "Says hello in chat now and then (an example plugin).")
            .num("Every (seconds)", 10.0, 1.0, 60.0, 1.0)
            .text("Message", "Hello from a plugin")
            .bool("Show on HUD", true)
            .bool("Box under me", false)
            .bool("Hold back hits", false),
    );

    p.on_enable("Hello", |game| api::chat(game, "Hello is on."));
    p.on_disable("Hello", |game| api::chat(game, "Hello is off."));

    // Every tick while Hello is on: the message every few seconds.
    p.on_tick(|game| {
        let Some(m) = api::module("Hello") else {
            return;
        };
        if game.ticks % (m.n("Every (seconds)") as u64 * 20) == 0 {
            api::chat(game, m.t("Message"));
            count(SAID);
        }
    });

    // .hello [times] | .hello stats | .hello total
    p.command("hello", "say Hello's message: .hello [times], .hello stats, .hello total", |game, args| {
        match args.first().copied() {
            Some("stats") => {
                let s = *STATS.lock().unwrap_or_else(|e| e.into_inner());
                api::chat(game, &format!("hud {} world {} blocked {} said {}", s[HUD], s[WORLD], s[BLOCKED], s[SAID]));
            }
            // A count kept in the plugin's data folder: it goes on across restarts.
            Some("total") => {
                let total = api::load(game, ID, "total").and_then(|t| t.parse::<u64>().ok()).unwrap_or(0) + 1;
                if let Err(e) = api::save(game, ID, "total", &total.to_string()) {
                    api::chat(game, &e);
                }
                api::chat(game, &format!(".hello total ran {total} times"));
            }
            times => {
                let Ok(times) = times.unwrap_or("1").parse::<u32>() else {
                    api::chat(game, "Use .hello [times], with a number of times from 1 to 5");
                    return;
                };
                let message = api::find_module("Hello").map_or(String::new(), |m| m.t("Message").to_owned());
                // One line now, the rest a second apart.
                for i in 0..times.clamp(1, 5) {
                    let message = message.clone();
                    api::after(u64::from(i) * 20, move |game| api::chat(game, &message));
                }
            }
        }
    });

    // Top left of the screen, below the module list's corner.
    p.on_hud(|game, draw| {
        if !api::module("Hello").is_some_and(|m| m.b("Show on HUD")) {
            return;
        }
        count(HUD);
        let text = match api::me(game) {
            Some(me) => format!("Hello: {:.0} hp at {:.0} {:.0} {:.0}", me.health, me.pos[0], me.pos[1], me.pos[2]),
            None => "Hello".to_owned(),
        };
        draw.rect([2.0, 60.0, api::text_width(game, &text) + 4.0, 12.0], 0x8000_0000);
        draw.label(&text, [4.0, 62.0], 0xFFD27F);
    });

    // A box round the block under you.
    p.on_world(|game, draw| {
        if !api::module("Hello").is_some_and(|m| m.b("Box under me")) {
            return;
        }
        let Some(me) = api::me(game) else {
            return;
        };
        let under = [me.pos[0].floor() as i32, me.pos[1].floor() as i32 - 1, me.pos[2].floor() as i32];
        if draw.block(under, 0xFFFF_A040) {
            count(WORLD);
        }
    });

    // Hold back hits: the attack packet never goes, so nothing you hit is hurt.
    p.on_packet_out(|_game, packet| {
        if api::module("Hello").is_some_and(|m| m.b("Hold back hits"))
            && matches!(packet.packet(), api::packets::Serverbound::Attack(_))
        {
            packet.cancel();
            count(BLOCKED);
        }
    });
}
