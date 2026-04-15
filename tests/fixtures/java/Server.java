import java.util.List;
import java.util.ArrayList;

public class Server {
    private int port;
    private String host;

    public Server(int port) {
        this.port = port;
        this.host = "localhost";
    }

    public void start() {
        System.out.println("Starting on " + host + ":" + port);
    }

    public List<String> getRoutes() {
        return new ArrayList<>();
    }
}
