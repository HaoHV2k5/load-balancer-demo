package com.example.gateway;

import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.IntStream;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.support.StaticListableBeanFactory;
import org.springframework.cloud.client.DefaultServiceInstance;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.loadbalancer.DefaultRequest;
import org.springframework.cloud.loadbalancer.core.RoundRobinLoadBalancer;
import org.springframework.cloud.loadbalancer.core.ServiceInstanceListSupplier;
import reactor.core.publisher.Flux;

import static org.assertj.core.api.Assertions.assertThat;

class RoundRobinTest {
    @Test
    void rotatesAcrossHealthyInstancesAndRejoinsRecoveredInstance() {
        ServiceInstance one = instance(1);
        ServiceInstance two = instance(2);
        ServiceInstance three = instance(3);
        AtomicReference<List<ServiceInstance>> healthy = new AtomicReference<>(List.of(three, one, two));
        ServiceInstanceListSupplier source = new ServiceInstanceListSupplier() {
            public String getServiceId() { return "demo-service"; }
            public Flux<List<ServiceInstance>> get() { return Flux.defer(() -> Flux.just(healthy.get())); }
        };
        var beans = new StaticListableBeanFactory();
        beans.addBean("supplier", new DemoLoadBalancerConfiguration.OrderedInstances(source));
        var balancer = new RoundRobinLoadBalancer(beans.getBeanProvider(ServiceInstanceListSupplier.class),
                "demo-service", -1);

        assertThat(nextPorts(balancer, 6)).containsExactly(8081, 8082, 8083, 8081, 8082, 8083);
        healthy.set(List.of(three, one));
        assertThat(nextPorts(balancer, 4)).containsExactly(8081, 8083, 8081, 8083);
        healthy.set(List.of(two, three, one));
        assertThat(nextPorts(balancer, 6)).containsExactly(8082, 8083, 8081, 8082, 8083, 8081);
        healthy.set(List.of());
        assertThat(balancer.choose(new DefaultRequest<>()).block().hasServer()).isFalse();
    }

    private ServiceInstance instance(int number) {
        return new DefaultServiceInstance("instance-" + number, "demo-service", "127.0.0.1", 8080 + number, false);
    }

    private List<Integer> nextPorts(RoundRobinLoadBalancer balancer, int count) {
        return IntStream.range(0, count).mapToObj(ignored -> balancer.choose(new DefaultRequest<>())
                .block().getServer().getPort()).toList();
    }
}
