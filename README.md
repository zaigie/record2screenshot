# Record2Screenshot API 使用说明

## 概述

这是一个将屏幕录制视频转换为长截图的异步 API 服务。支持上传视频文件，异步处理并返回拼接后的长图。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务器

```bash
python server.py
```

服务器启动后会在 `http://localhost:8000` 监听请求。

API 文档地址：`http://localhost:8000/docs`

## API 接口

### 1. 上传视频 (POST /upload)

上传视频文件并启动异步转换任务。

**请求参数：**

- `file`: 视频文件 (必需)
- `crop_top`: 顶部裁剪比例 (默认: 0.15)
- `crop_bottom`: 底部裁剪比例 (默认: 0.15)
- `expect_offset`: 期望偏移比例 (默认: 0.3)
- `min_overlap`: 最小重叠比例 (默认: 0.15)
- `approx_diff`: 近似差异阈值 (默认: 1.0)
- `transpose`: 水平滚动模式 (默认: false)
- `seam_width`: 调试缝合线宽度 (默认: 0)
- `verbose`: 详细输出 (默认: false)

**响应示例：**

```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "任务已创建，正在处理中"
}
```

### 2. 查询任务状态 (GET /status/{task_id})

查询指定任务的处理状态。

**响应示例：**

```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "created_at": "2023-11-20T10:30:00",
  "completed_at": "2023-11-20T10:32:15",
  "error_message": null
}
```

**状态说明：**

- `pending`: 等待处理
- `processing`: 正在处理
- `completed`: 处理完成
- `failed`: 处理失败

### 3. 获取结果图片 (GET /result/{task_id})

下载处理完成的长截图。

**注意：** 只有状态为 `completed` 的任务才能下载结果。

### 4. 列出所有任务 (GET /tasks)

获取任务列表，支持分页。

**查询参数：**

- `page`: 页码（从 1 开始，默认为 1）
- `page_size`: 每页数量（1-100，默认为 20）

**响应示例：**

```json
{
  "tasks": [
    {
      "task_id": "123e4567-e89b-12d3-a456-426614174000",
      "status": "completed",
      "created_at": "2023-11-20T10:30:00",
      "completed_at": "2023-11-20T10:32:15",
      "file_name": "screen_recording.mp4",
      "file_size_mb": 25.6
    }
  ],
  "total_count": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### 5. 删除任务 (DELETE /task/{task_id})

删除指定任务和相关文件。

## 数据存储

API 服务使用 SQLite 数据库来持久化存储任务信息，确保服务重启后任务状态不丢失。

**数据库文件：** `data/tasks.db`

**目录结构：**

```
record2screenshot/
├── data/              # 数据目录（持久化存储）
│   └── tasks.db      # 任务数据库文件
├── output/           # 输出图片目录
└── ...
```

**任务表结构：**

- `task_id`: 任务唯一标识符（主键）
- `status`: 任务状态（pending/processing/completed/failed）
- `created_at`: 创建时间
- `completed_at`: 完成时间
- `result_path`: 结果文件路径
- `error_message`: 错误信息
- `file_name`: 原始文件名
- `file_size_mb`: 文件大小（MB）

**分页查询：**

- 默认每页 20 条记录
- 最大每页 100 条记录
- 支持按创建时间倒序排列

## 使用示例

### curl 命令示例

```bash
# 上传视频
curl -X POST "http://localhost:8000/upload" \
  -F "file=@screen_recording.mp4" \
  -F "crop_top=0.15" \
  -F "verbose=true"

# 查询状态 (替换为实际的task_id)
curl "http://localhost:8000/status/123e4567-e89b-12d3-a456-426614174000"

# 获取任务列表（第1页，每页20条）
curl "http://localhost:8000/tasks"

# 获取任务列表（第2页，每页10条）
curl "http://localhost:8000/tasks?page=2&page_size=10"

# 下载结果
curl -O "http://localhost:8000/result/123e4567-e89b-12d3-a456-426614174000"
```

## 命令行工具

除了 API 服务，也可以直接使用命令行工具：

```bash
python convert.py input_video.mp4 -o output.jpg
```

## 参数说明

- **crop_top/crop_bottom**: 裁剪顶部/底部的比例，用于去除固定的头部/底部栏
- **expect_offset**: 期望的滚动偏移比例，影响算法的预测精度
- **min_overlap**: 最小重叠区域比例，确保帧间有足够的重叠进行匹配
- **approx_diff**: 近似差异阈值，控制匹配的精确度
- **transpose**: 是否为水平滚动模式（默认为垂直滚动）
- **seam_width**: 调试时显示缝合线的宽度
- **verbose**: 是否输出详细的处理信息

## Docker 部署

### 构建 Docker 镜像

```bash
# 构建镜像
docker build -t record2screenshot .

# 或指定标签
docker build -t record2screenshot:latest .
```

### 运行 Docker 容器

#### 基本运行

```bash
# 运行容器（前台运行）
docker run -p 8000:8000 record2screenshot

# 后台运行
docker run -d -p 8000:8000 --name record2screenshot-app record2screenshot
```

#### 修改并发

默认同时处理 2 个任务，如需更改并发，指定环境变量 MAX_CONCURRENCY 即可：

```bash
docker run -d -p 8000:8000 \
  -e MAX_CONCURRENCY=6 \
  --name record2screenshot-app \
  record2screenshot
```

#### 持久化数据存储

**方案一：仅持久化输出文件**

```bash
# 仅挂载输出目录
docker run -d -p 8000:8000 \
  -v $(pwd)/output:/app/output \
  --name record2screenshot-app \
  record2screenshot
```

**方案二：完整的数据持久化（推荐）**

```bash
# 同时挂载数据目录和输出目录
docker run -d -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  --name record2screenshot-app \
  record2screenshot
```

**创建本地目录并运行：**

```bash
# 创建必要的目录
mkdir -p data output

# 运行容器并挂载目录
docker run -d -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -e MAX_CONCURRENCY=4 \
  --name record2screenshot-app \
  record2screenshot
```

**目录映射说明：**

- `/app/data` - 数据库文件存储目录
- `/app/output` - 生成的截图文件存储目录

## 注意事项

1. 服务器使用进程池处理视频，最多同时处理 2 个任务，可修改环境变量设置
2. 上传的视频文件会在处理完成后自动删除
3. 结果图片保存在 `output/` 目录下
4. 对于超高的图片，会自动分割成多个文件保存
5. 确保系统已安装 ffmpeg（Docker 镜像中已包含）
6. Docker 容器默认监听 8000 端口，可通过 `-p` 参数映射到其他端口
7. 任务信息使用 SQLite 数据库持久化存储，数据库文件为 `data/tasks.db`
8. 首次运行时会自动创建 `data` 目录、数据库文件和表结构
9. 删除任务时会同时删除数据库记录和结果文件
10. 使用 Docker 部署时，建议映射 `data` 目录以持久化任务数据
