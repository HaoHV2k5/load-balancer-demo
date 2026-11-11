package com.example.gateway;

import java.util.List;

import org.springframework.cloud.loadbalancer.core.ServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.support.LoadBalancerClientFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
public class InstancesController {
    private final LoadBalancerClientFactory factory;

    public InstancesController(LoadBalancerClientFactory factory) {
        this.factory = factory;
    }

    @GetMapping("/api/demo/instances")
    public Mono<List<InstanceView>> instances() {
        // Inspect the actual supplier used for routing, without advancing the round-robin counter.
        return factory.getInstance("demo-service", ServiceInstanceListSupplier.class).get().next()
                .map(instances -> instances.stream()
                        .map(instance -> new InstanceView(instance.getInstanceId(), instance.getPort()))
                        .toList());
    }

    public record InstanceView(String instanceId, int port) { }
}
