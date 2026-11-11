# Spring Load Balancing Demo

Demo chạy thật với **Spring Boot 3.5.16**, **Spring Cloud Gateway**, **Spring Cloud LoadBalancer** và **Actuator**. Không cần Docker, Eureka hay database.

```text
                              ┌─ instance-1 :8081 ─ /api/hello, /api/actuator/health
Client → Gateway :8080 ────────┼─ instance-2 :8082 ─ /api/hello, /api/actuator/health
         GET /api/hello        └─ instance-3 :8083 ─ /api/hello, /api/actuator/health
         RoundRobinLoadBalancer + health checks mỗi 2 giây
```

Đây là client-side load balancing ở gateway: gateway chọn backend rồi proxy HTTP request. Danh sách địa chỉ đăng ký tĩnh bằng `SimpleDiscoveryClient`; trạng thái sống/chết được kiểm tra động. Mỗi instance là một JVM riêng, chạy cùng JAR với port và tên khác nhau. Các ứng dụng chỉ bind `127.0.0.1` để trình diễn trên máy local.

## Cài đặt

### 1. Chuẩn bị môi trường

| Công cụ | Yêu cầu | Mục đích |
| --- | --- | --- |
| JDK | 17 trở lên; có thể dùng JDK 21 | Build và chạy ứng dụng Spring |
| Maven | 3.6.3 trở lên | Tải dependency, build và chạy test |
| Python | 3.9 trở lên | Chạy script điều khiển demo |
| Git | Có lệnh `git` | Clone repository |
| Bash | macOS, Linux hoặc WSL trên Windows | Chạy `demo.sh` |

Nếu chưa có công cụ, cài theo hướng dẫn chính thức: [JDK (Eclipse Temurin)](https://adoptium.net/installation/), [Maven](https://maven.apache.org/install.html), [Python](https://www.python.org/downloads/). Thiết lập `JAVA_HOME` trỏ đến thư mục JDK nếu cần và bảo đảm các lệnh có trong `PATH`. Trên Windows, chạy script trong WSL với các công cụ được cài bên trong WSL.

Kiểm tra môi trường bằng terminal mới:

```bash
java -version
mvn -v
python3 --version
git --version
```

Python chỉ dùng thư viện chuẩn, không cần `pip install`. Gateway và service đều viết bằng Java/Spring. Lần build đầu cần Internet tải dependency Maven; các cổng `8080–8083` cần trống.

### 2. Tải mã nguồn

```bash
git clone https://github.com/HaoHV2k5/load-balancer-demo.git
cd load-balancer-demo
chmod +x demo.sh
```

Nếu đã có mã nguồn, mở terminal tại thư mục gốc chứa `pom.xml` và `demo.sh`. Các lệnh bên dưới đều chạy từ thư mục này.

### 3. Build project

```bash
./demo.sh build
```

Lệnh trên chạy `mvn package`, bao gồm unit test, và tạo hai file:

```text
demo-service/target/demo-service.jar
gateway/target/gateway.jar
```

Build thành công hiển thị `BUILD SUCCESS`. Có thể dùng trực tiếp `mvn package` nếu không dùng script.

## Chạy ứng dụng (Run)

```bash
./demo.sh up
./demo.sh status
```

`up` chạy nền ba instance ở `8081/8082/8083` và gateway ở `8080`, sau đó chờ health check. Khi sẵn sàng, terminal hiển thị `Demo ready`; `status` có đủ bốn ứng dụng `UP` và ba backend trong `Gateway eligible`.

Trên macOS, có thể thay lệnh `up` bằng lệnh sau để tự mở bốn cửa sổ log:

```bash
./demo.sh up --terminals
```

`up` tự build nếu chưa có JAR. Sau khi sửa code hoặc YAML, chạy lần lượt `./demo.sh down`, `./demo.sh build`, rồi `./demo.sh up` để dùng bản mới. Nếu đang chạy Java thủ công, Ctrl+C các process đó trước khi dùng `up`.

## Hướng dẫn sử dụng (HDSD)

| Lệnh | Công dụng |
| --- | --- |
| `./demo.sh requests 12` | Gửi 12 request qua gateway và thống kê phân phối |
| `./demo.sh status` | Xem health và danh sách backend gateway đang dùng |
| `./demo.sh logs --requests-only` | Theo dõi log xử lý request của các backend |
| `./demo.sh logs 1` | Xem log instance-1; có thể đổi thành `2`, `3`, `gateway` |
| `./demo.sh terminals` | Mở bốn cửa sổ log trên macOS khi demo đã chạy |
| `./demo.sh crash 2` | Kill đột ngột instance-2 |
| `./demo.sh stop 2` | Dừng instance-2 bằng SIGTERM |
| `./demo.sh start 2` | Chạy lại instance-2 |
| `./demo.sh verify` | Tự động kiểm tra Round Robin, failure và recovery |
| `./demo.sh down` | Dừng các JVM do script tạo |
| `./demo.sh --help` | Xem các lệnh hỗ trợ |

Gọi API bằng trình duyệt, Postman hoặc curl:

```bash
curl -s http://localhost:8080/api/hello
```

Ví dụ response (counter và thời gian thay đổi theo lần chạy):

```json
{
  "instanceId": "instance-1",
  "port": 8081,
  "requestCount": 1,
  "requestId": "manual",
  "timestamp": "2026-11-11T02:00:00Z"
}
```

Response còn có header `X-Instance-Id`. `requestCount` là số request `/api/hello` của riêng JVM đó, reset khi restart; health check không làm tăng counter.

## Đường dẫn API thống nhất

| Endpoint | Địa chỉ |
| --- | --- |
| Gọi nghiệp vụ qua gateway | `http://localhost:8080/api/hello` |
| Gọi trực tiếp backend | `http://localhost:8081/api/hello` (hoặc 8082/8083) |
| Xem backend gateway đang dùng | `http://localhost:8080/api/demo/instances` |
| Health của gateway/backend | `http://localhost:<port>/api/actuator/health` |
| Info của gateway/backend | `http://localhost:<port>/api/actuator/info` |

Gateway giữ nguyên `/api/hello` khi chuyển đến backend; route không dùng `StripPrefix`. Actuator được đặt `management.endpoints.web.base-path: /api/actuator` ở cả hai module; health supplier và script cũng dùng đường dẫn mới.

Trong `lb://demo-service`, `lb` viết tắt của **Load Balancer**. `demo-service` là tên nhóm backend khai báo dưới `spring.cloud.discovery.client.simple.instances`, đồng thời khớp `name` trong `@LoadBalancerClient`. Thuộc tính `id` của route chỉ là tên quy tắc và có thể đặt khác.

## Demo Round Robin Load Balancing

### 1. Starting Multiple Service Instances

```bash
./demo.sh up
./demo.sh status
```

Quan sát gateway `8080`, ba service `8081/8082/8083` đều `UP`; `Gateway eligible` có đủ ba instance. Danh sách này lấy trực tiếp từ supplier mà LoadBalancer dùng để chọn backend.

### 2. Sending Multiple HTTP Requests

```bash
./demo.sh requests 12
```

Script gửi request **tuần tự**, in instance/port/counter/request ID và thống kê cuối đợt:

```text
01  HTTP 200  -> instance-1  port=8081 ...
02  HTTP 200  -> instance-2  port=8082 ...
03  HTTP 200  -> instance-3  port=8083 ...
04  HTTP 200  -> instance-1  port=8081 ...
...
Distribution: {"instance-1": 4, "instance-2": 4, "instance-3": 4} errors=0
```

### 3. Observing Request Distribution

Mở terminal thứ hai để xem log request thực tế ở các backend, mỗi dòng có nhãn instance và port:

```bash
./demo.sh logs --requests-only --lines 0
```

Mỗi dòng log ghi `requestId`, instance, port và counter để đối chiếu với terminal gửi request.

Xem riêng từng ứng dụng bằng `./demo.sh logs 1`, `logs 2`, `logs 3` hoặc `logs gateway`. Dùng `./demo.sh logs` để xem tất cả log, `--lines 100` để lấy thêm lịch sử, `--no-follow` để in xong rồi thoát. Ctrl+C chỉ dừng màn hình xem log; service vẫn chạy. Log được ghi nối tiếp qua các lần restart. Các lệnh xem log chỉ đọc file trong `.demo/` do script ghi; nếu chạy Java thủ công, xem tại terminal tương ứng.

Danh sách lệnh và hướng dẫn trình diễn bằng hai terminal có trong [LENH_DEMO.txt](LENH_DEMO.txt).

Trên macOS, dùng `./demo.sh up --terminals` để khởi động demo và tự mở bốn cửa sổ Terminal.app trước bước chờ health check, mỗi cửa sổ xem log một instance hoặc gateway. Nếu demo đã chạy, dùng `./demo.sh terminals` để mở các cửa sổ log; `./demo.sh terminals 2` chỉ mở log instance-2. Có thể thêm `--requests-only` và `--lines 0`, hoặc `--dry-run` để xem trước lệnh. Các cửa sổ này chỉ theo dõi log của JVM chạy nền; Ctrl+C hoặc đóng cửa sổ không dừng service. Chạy lệnh lại sẽ mở thêm cửa sổ. Nếu macOS hỏi quyền điều khiển Terminal, cần cho phép ứng dụng đang chạy lệnh.

### 4. Verifying Round Robin Behavior

Kiểm tra cả **thứ tự lặp vòng** và **số lượng chia đều**: `1 → 2 → 3 → 1 → 2 → 3`. Với 12 request và ba instance khỏe, mỗi instance nhận bốn request.

Gateway mới khởi động được cấu hình bắt đầu từ instance-1. Nếu đã gửi request trước đó, đợt tiếp theo có thể bắt đầu ở instance-2 hoặc instance-3; vẫn đúng Round Robin. Khi danh sách khỏe thay đổi, không yêu cầu vòng mới bắt đầu từ instance-1. Để quan sát rõ thứ tự, tránh gửi request từ terminal khác đồng thời.

## Demo Instance Failure & Recovery

### 1. Simulating Instance Failure

Giữ gateway và instance-1/3 hoạt động, kill thật process của instance-2:

```bash
./demo.sh crash 2
```

`crash` dùng `SIGKILL`, tương đương service chết đột ngột. Có thể dùng `./demo.sh stop 2` để dừng bằng `SIGTERM`.

### 2. Observing LoadBalancer Behavior

```bash
./demo.sh status
./demo.sh requests 12
```

Chạy `status` đến khi `Gateway eligible` chỉ còn `instance-1, instance-3`, rồi gửi 12 request: hai instance còn lại nhận **6 request mỗi instance**, luân phiên `1 → 3 → 1 → 3`. Instance-2 không nhận request.

Ngay sau khi kill và **trước khi health check phát hiện**, một số request có thể trả `5xx`. Demo không bật retry để quan sát được khoảng phát hiện lỗi. Đây không phải cơ chế failover tức thời; sau khi danh sách ổn định, request chỉ đi đến instance còn khỏe.

### 3. Health Check Mechanism

```bash
curl -s http://localhost:8081/api/actuator/health
curl -s http://localhost:8082/api/actuator/health
curl -s http://localhost:8080/api/demo/instances
```

- `HealthCheckServiceInstanceListSupplier` gọi `/api/actuator/health` mỗi **2 giây**, với connect/response timeout **1 giây** cho probe.
- Backend trả HTTP thành công được xem là khỏe; Actuator trả `503` khi `DOWN`/`OUT_OF_SERVICE`, hoặc probe gặp lỗi kết nối, sẽ bị loại khỏi danh sách.
- Khi một backend tắt, thường cần vài giây để cập nhật; dùng `/api/demo/instances` xác nhận thay vì giả định đúng hai giây.
- Gateway vẫn giữ các địa chỉ cấu hình và tiếp tục probe cả instance đã chết. Khi process chạy lại, nó tự được thêm vào danh sách khỏe.
- Tắt cache LoadBalancer bổ sung vì health supplier đã lưu kết quả probe. Chờ cả đợt probe hoàn tất rồi xuất một danh sách, sắp xếp theo port để vòng Round Robin ổn định.
- `/api/actuator/health` của gateway chỉ phản ánh sức khỏe gateway; `/api/demo/instances` mới là danh sách backend dùng để routing.

### 4. Instance Recovery and Redistribution

```bash
./demo.sh start 2
./demo.sh status
./demo.sh requests 12
```

Sau khi `Gateway eligible` có đủ ba instance trở lại, 12 request tiếp theo chia **4/4/4**. Không restart gateway. Counter instance-2 bắt đầu lại vì đó là một JVM mới.

## Kiểm chứng tự động

```bash
./demo.sh verify
```

Lệnh này khởi động demo nếu cần, kiểm tra luân phiên và chia đều trên ba instance, kill instance-2, chờ supplier loại nó, kiểm tra hai instance còn lại, restart instance-2 và kiểm tra chia lại ba instance. Sau đó tắt cả ba backend để xác nhận HTTP `503`, phục hồi cả ba và kiểm tra routing lần cuối. Kết thúc thành công in `ALL CHECKS PASSED` và để demo tiếp tục chạy.

**Lưu ý:** `verify` chủ động dừng/chạy lại các process của demo và reset counter backend. Script chỉ gửi signal cho PID có command khớp đường dẫn JAR của project và port tương ứng.

## Dừng demo

```bash
./demo.sh down
```

Log và PID lưu trong `.demo/` (đã gitignore). Chạy `./demo.sh --help` để xem các lệnh. Nếu startup lỗi, đọc `.demo/gateway.log` hoặc `.demo/1.log`, `.demo/2.log`, `.demo/3.log`.

## Chạy bằng Java trực tiếp / IDE

Sau `mvn package`, mở bốn terminal:

```bash
# Terminal 1
java -jar demo-service/target/demo-service.jar --server.port=8081 --demo.instance-id=instance-1
# Terminal 2
java -jar demo-service/target/demo-service.jar --server.port=8082 --demo.instance-id=instance-2
# Terminal 3
java -jar demo-service/target/demo-service.jar --server.port=8083 --demo.instance-id=instance-3
# Terminal 4
java -jar gateway/target/gateway.jar
```

Hoặc tạo ba run configuration cho `DemoServiceApplication` với các program argument tương ứng, và một cho `GatewayApplication`. Ctrl+C terminal instance-2 để dừng, chạy lại cùng lệnh để recovery. Các lệnh `requests`/`status` vẫn dùng được; `start`/`stop`/`crash`/`down` quản lý process do script tạo, nên hãy thao tác lifecycle trong terminal/IDE nếu chạy thủ công. Dùng `verify` với các process do script tạo.

## Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| `java`, `mvn` hoặc `python3`: command not found | Cài công cụ tương ứng, kiểm tra `PATH`, mở lại terminal |
| `Permission denied` khi chạy `demo.sh` | Chạy `chmod +x demo.sh` |
| `Unable to access jarfile` | Build trước và chạy lệnh Java từ thư mục gốc; nếu đang ở `demo-service/target`, dùng `java -jar demo-service.jar` |
| Port `8080–8083` đang được sử dụng | Dừng demo bằng `down`; với JVM chạy thủ công, Ctrl+C tại terminal tương ứng |
| Chỉ thấy `da chay` hoặc báo đang chạy bản cũ | Chạy `down`, `build`, rồi `up`; process còn sống chưa đồng nghĩa health endpoint đã sẵn sàng |
| Không thấy cửa sổ log | Trên macOS dùng `./demo.sh terminals`; có thể xem ngay trong terminal hiện tại bằng `./demo.sh logs` |
| Request lỗi ngay sau khi kill instance | Chờ `status` loại instance chết khỏi `Gateway eligible`, rồi gửi lại request |

## Các file chính

| File | Vai trò |
| --- | --- |
| `demo-service/.../HelloController.java` | Response định danh instance, counter và log request |
| `gateway/.../DemoLoadBalancerConfiguration.java` | Round Robin thật của Spring, health probes, thứ tự instance ổn định |
| `gateway/.../InstancesController.java` | Quan sát danh sách backend mà gateway đang dùng |
| `gateway/src/main/resources/application.yml` | Địa chỉ instance, route `lb://`, chu kỳ health check |
| `gateway/.../RoundRobinTest.java` | Test vòng chia request khi remove/rejoin instance và danh sách rỗng |
| `scripts/demo.py` | Chạy/dừng JVM, gửi request, thống kê và kiểm chứng end-to-end |

Tài liệu chính thức: [Spring Cloud LoadBalancer](https://docs.spring.io/spring-cloud-commons/reference/4.3/spring-cloud-commons/loadbalancer.html), [Gateway WebFlux starter](https://docs.spring.io/spring-cloud-gateway/reference/4.3/spring-cloud-gateway-server-webflux/starter.html), [Spring Boot / Cloud compatibility](https://spring.io/projects/spring-cloud/).
