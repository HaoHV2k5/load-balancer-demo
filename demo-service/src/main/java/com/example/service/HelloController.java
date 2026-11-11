package com.example.service;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloController {
    private static final Logger log = LoggerFactory.getLogger(HelloController.class);
    private final AtomicLong counter = new AtomicLong();
    private final String instanceId;
    private final int port;

    public HelloController(@Value("${demo.instance-id}") String instanceId,
                           @Value("${server.port}") int port) {
        this.instanceId = instanceId;
        this.port = port;
    }

    @GetMapping("/api/hello")
    public ResponseEntity<HelloResponse> hello(
            @RequestHeader(value = "X-Request-Id", defaultValue = "manual") String requestId) {
        long count = counter.incrementAndGet();
        log.info("requestId={} handled by {} port={} requestCount={}", requestId, instanceId, port, count);
        return ResponseEntity.ok()
                .header("X-Instance-Id", instanceId)
                .body(new HelloResponse(instanceId, port, count, requestId, Instant.now()));
    }

    public record HelloResponse(String instanceId, int port, long requestCount,
                                String requestId, Instant timestamp) { }
}
