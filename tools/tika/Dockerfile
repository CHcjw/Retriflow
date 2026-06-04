FROM eclipse-temurin:17-jre

WORKDIR /app

COPY tools/tika/tika-server-standard-3.2.3.jar /app/tika-server-standard-3.2.3.jar

EXPOSE 9998

CMD ["java", "-jar", "/app/tika-server-standard-3.2.3.jar", "--port", "9998"]
