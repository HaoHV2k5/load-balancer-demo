package com.example.gateway;

import java.time.Duration;
import java.util.Comparator;
import java.util.List;

import io.netty.channel.ChannelOption;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.loadbalancer.core.DelegatingServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.core.RoundRobinLoadBalancer;
import org.springframework.cloud.loadbalancer.core.ServiceInstanceListSupplier;
import org.springframework.cloud.loadbalancer.support.LoadBalancerClientFactory;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.netty.http.client.HttpClient;

// Deliberately no @Configuration: these beans belong only to the demo-service child context.
public class DemoLoadBalancerConfiguration {
    @Bean
    ServiceInstanceListSupplier serviceInstanceListSupplier(ConfigurableApplicationContext context) {
        WebClient healthClient = WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(HttpClient.create()
                        .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 1000)
                        .responseTimeout(Duration.ofSeconds(1))))
                .build();
        ServiceInstanceListSupplier healthSupplier = ServiceInstanceListSupplier.builder()
                .withDiscoveryClient()
                .withHealthChecks(healthClient)
                .build(context);
        return new OrderedInstances(healthSupplier);
    }

    @Bean
    RoundRobinLoadBalancer roundRobinLoadBalancer(Environment environment, LoadBalancerClientFactory factory) {
        String serviceId = environment.getRequiredProperty(LoadBalancerClientFactory.PROPERTY_NAME);
        // Seed -1 makes the first request select index 0, for an easy-to-follow presentation.
        return new RoundRobinLoadBalancer(factory.getLazyProvider(serviceId, ServiceInstanceListSupplier.class),
                serviceId, -1);
    }

    static class OrderedInstances extends DelegatingServiceInstanceListSupplier {
        OrderedInstances(ServiceInstanceListSupplier delegate) {
            super(delegate);
        }

        @Override
        public Flux<List<ServiceInstance>> get() {
            // Parallel health probes may finish in any order. Keep the round-robin ring stable.
            return delegate.get().map(instances -> instances.stream()
                    .sorted(Comparator.comparingInt(ServiceInstance::getPort)).toList());
        }
    }
}
