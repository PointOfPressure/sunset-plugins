// Once a tick: hands the game to the plugin. Leave this file as it is.
fn myplugin_tick(game: &mut crate::game::Game<'_>) {
    crate::game::myplugin_plugin::tick(game);
}
