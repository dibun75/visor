#include <iostream>
#include <string>

class Server {
public:
    int port;
    std::string host;

    Server(int p) : port(p), host("localhost") {}

    void start() {
        std::cout << "Starting on " << host << ":" << port << std::endl;
    }
};

void handleRequest(const std::string& path) {
    std::cout << "Handling: " << path << std::endl;
}
