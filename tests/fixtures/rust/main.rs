use std::collections::HashMap;

struct Config {
    host: String,
    port: u16,
}

impl Config {
    fn new(host: &str, port: u16) -> Self {
        Config { host: host.to_string(), port }
    }
}

fn start_server(config: &Config) {
    println!("Starting on {}:{}", config.host, config.port);
}

fn parse_args(args: &[String]) -> HashMap<String, String> {
    let mut map = HashMap::new();
    map.insert("host".to_string(), args[0].clone());
    map
}
