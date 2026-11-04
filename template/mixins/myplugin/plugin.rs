// My Module: a Sunset plugin. Change what it does in `setup`.

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
