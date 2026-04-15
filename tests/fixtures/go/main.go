package main

import (
	"fmt"
	"net/http"
)

type Server struct {
	Port int
	Host string
}

func NewServer(port int) *Server {
	return &Server{Port: port, Host: "localhost"}
}

func (s *Server) Start() {
	addr := fmt.Sprintf("%s:%d", s.Host, s.Port)
	http.ListenAndServe(addr, nil)
}

func handleRequest(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintf(w, "Hello!")
}
