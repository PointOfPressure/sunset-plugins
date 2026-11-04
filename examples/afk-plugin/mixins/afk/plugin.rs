// AFK Fisher, an example Sunset plugin (plugin API 2) for unattended play: it turns on Sunset's Auto Fish, counts the
// fish, and when something is wrong (low health, death, a player coming near) stops everything and logs out. Horizon's
// Auto-reconnect brings you back after a server restart, and the fishing goes on.

use super::Game;
use super::sunset_api as api;
use std::sync::Mutex;

const _: () = api::needs(2);

const ID: &str = "afk";
const NAME: &str = "AFK Fisher";
const FISH: &str = "cod,salmon,tropical_fish,pufferfish";

pub(super) fn tick(game: &mut Game<'_>) {
    api::plugin(game, ID, "0.1.0", setup);
}

// The plugin's state lives as long as the game: it outlasts disconnects and reconnects.
struct Afk {
    seconds: u64,
    caught: u64,
    total: u64,
    // Fish in the inventory at the last count.
    held: u32,
    task: Option<u64>,
    last_stop: String,
    last_disconnect: String,
}

static AFK: Mutex<Afk> = Mutex::new(Afk {
    seconds: 0,
    caught: 0,
    total: 0,
    held: 0,
    task: None,
    last_stop: String::new(),
    last_disconnect: String::new(),
});

fn afk<R>(f: impl FnOnce(&mut Afk) -> R) -> R {
    f(&mut AFK.lock().unwrap_or_else(|e| e.into_inner()))
}

fn setup(p: &mut api::Plugin) {
    p.module(
        api::Module::new(NAME, api::Category::Player, "Fishes while you are away and logs out on danger (an example plugin).")
            .num("Leave below health", 10.0, 1.0, 19.0, 1.0)
            .bool("Leave when a player comes", true)
            .num("Player range", 32.0, 4.0, 128.0, 4.0)
            .bool("Log out", true)
            .bool("Auto reconnect", true)
            .num("Stop after (minutes)", 0.0, 0.0, 720.0, 5.0),
    );
    p.on_enable(NAME, start);
    p.on_disable(NAME, finish);
    p.on_hurt(|game, h| {
        let Some(m) = api::module(NAME) else {
            return;
        };
        let below = m.n("Leave below health") as f32;
        // At 0 it is a death: on_death has it.
        if h.health > 0.0 && h.health < below {
            danger(game, &format!("health {:.0} is below {below:.0}", h.health));
        }
    });
    p.on_death(|game| {
        if api::is_on(NAME) {
            danger(game, "you died");
        }
    });
    p.on_disconnect(|_game, d| {
        let how = if d.retry {
            "reconnecting"
        } else if d.by_server {
            "by the server, not retried"
        } else {
            "connection lost, not retried"
        };
        afk(|a| a.last_disconnect = format!("{} ({how})", d.reason));
    });
    p.on_join(|game| {
        if api::is_on(NAME) {
            api::chat(game, "AFK Fisher: back in, fishing again.");
        }
    });
    p.on_stop(|_game, why| afk(|a| a.last_stop = why.to_owned()));
    p.on_hud(|game, draw| {
        if !api::is_on(NAME) {
            return;
        }
        let (caught, total, s) = afk(|a| (a.caught, a.total, a.seconds));
        let text = format!("AFK Fisher: {caught} fish ({total} in all), {}h {:02}m", s / 3600, s / 60 % 60);
        draw.rect([2.0, 76.0, api::text_width(game, &text) + 4.0, 12.0], 0x8000_0000);
        draw.label(&text, [4.0, 78.0], 0x7FD2FF);
    });
    p.command("afk", "AFK Fisher: .afk shows how it is going, .afk reset clears the all-time count", |game, args| {
        if args.first() == Some(&"reset") {
            afk(|a| a.total = 0);
            if let Err(e) = api::save(game, ID, "total", "0") {
                api::chat(game, &e);
            }
        }
        let (caught, total, s, stop, left) = afk(|a| (a.caught, a.total, a.seconds, a.last_stop.clone(), a.last_disconnect.clone()));
        let on = |b: bool| if b { "on" } else { "off" };
        api::chat(game, &format!(
            "AFK Fisher {}: {caught} fish, {total} in all, {s} s; Auto Fish {}; auto reconnect {}",
            on(api::is_on(NAME)),
            on(api::is_on("Auto Fish")),
            on(api::auto_reconnect_on(game)),
        ));
        api::chat(game, &format!("Last stop: {}", if stop.is_empty() { "none" } else { &stop }));
        api::chat(game, &format!("Last disconnect: {}", if left.is_empty() { "none" } else { &left }));
    });
}

fn start(game: &mut Game<'_>) {
    if !api::find_item(game, "fishing_rod").is_some_and(|slot| slot < 9) {
        api::chat(game, "AFK Fisher: put a fishing rod in your hotbar first.");
        let _ = api::toggle(game, NAME, false);
        return;
    }
    let Some(m) = api::module(NAME) else {
        return;
    };
    if m.b("Auto reconnect") {
        api::auto_reconnect(game, true);
    }
    // Auto Fish does the fishing: casting, reeling in, switching to the rod.
    for (setting, value) in [("Auto cast", true), ("Auto switch", true)] {
        if let Err(e) = api::set(game, "Auto Fish", setting, value) {
            api::chat(game, &e);
        }
    }
    if let Err(e) = api::toggle(game, "Auto Fish", true) {
        api::chat(game, &e);
    }
    let total = api::load(game, ID, "total").and_then(|t| t.parse().ok()).unwrap_or(0);
    let held = api::count(game, FISH);
    let task = api::every(20, second);
    afk(|a| {
        if let Some(old) = a.task.replace(task) {
            api::cancel(old);
        }
        a.seconds = 0;
        a.caught = 0;
        a.total = total;
        a.held = held;
    });
    let near = if m.b("Leave when a player comes") { format!(" or a player comes within {:.0} blocks", m.n("Player range")) } else { String::new() };
    api::chat(game, &format!("AFK Fisher on: fishing; leaves below {:.0} health{near}.", m.n("Leave below health")));
}

fn finish(game: &mut Game<'_>) {
    if let Some(task) = afk(|a| a.task.take()) {
        api::cancel(task);
    }
    let _ = api::toggle(game, "Auto Fish", false);
}

// Once a second while on: count the catch, look for danger, watch the time.
fn second(game: &mut Game<'_>) {
    let Some(m) = api::module(NAME) else {
        return;
    };
    let fish = api::count(game, FISH);
    let (total, seconds, more) = afk(|a| {
        let more = fish > a.held;
        if more {
            a.caught += u64::from(fish - a.held);
            a.total += u64::from(fish - a.held);
        }
        a.held = fish;
        a.seconds += 1;
        (a.total, a.seconds, more)
    });
    if more && let Err(e) = api::save(game, ID, "total", &total.to_string()) {
        api::chat(game, &e);
    }
    if m.b("Leave when a player comes") {
        let range = m.n("Player range");
        if let Some(p) = api::players(game).into_iter().find(|p| !p.friend && p.distance <= range) {
            danger(game, &format!("{} came within {:.0} blocks", p.name, p.distance));
            return;
        }
    }
    let minutes = m.n("Stop after (minutes)");
    if minutes > 0.0 && seconds as f64 >= minutes * 60.0 {
        api::stop_everything(game, "AFK Fisher: time is up");
    }
}

// Something is wrong: everything off (so nothing keeps acting) and, with Log out, off the server.
fn danger(game: &mut Game<'_>, why: &str) {
    let log_out = api::module(NAME).is_some_and(|m| m.b("Log out"));
    api::stop_everything(game, &format!("AFK Fisher: {why}"));
    if log_out {
        api::disconnect(game);
    }
}
