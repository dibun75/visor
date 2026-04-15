#include <stdio.h>
#include <stdlib.h>

struct Config {
    int port;
    char host[256];
};

void start_server(struct Config *config) {
    printf("Starting on %s:%d\n", config->host, config->port);
}

int parse_port(const char *str) {
    return atoi(str);
}
