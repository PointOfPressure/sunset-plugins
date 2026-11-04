// Once a tick: hands the game to the plugin.
fn afk_tick(game: &mut crate::game::Game<'_>) {
    crate::game::afk_plugin::tick(game);
}
