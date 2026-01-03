#!/bin/bash

echo "Waiting for PostgreSQL to be ready..."

# 等待PostgreSQL
while ! nc -z db 5432; do
  sleep 1
done

echo "PostgreSQL is ready!"

echo "Waiting for Redis to be ready..."

# 等待Redis
while ! nc -z redis 6379; do
  sleep 1
done

echo "Redis is ready!"

# 执行传入的命令
exec "$@"