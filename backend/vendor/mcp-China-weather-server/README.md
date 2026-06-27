# MCP 天气预报服务器

基于高德地图API的MCP (Model Context Protocol) 天气预报服务器，使用TypeScript开发。

## 🌟 功能特性

- ✅ **实时天气查询** - 获取指定城市的当前天气状况
- ✅ **天气预报查询** - 获取未来几天的天气预报
- ✅ **智能城市识别** - 支持中国市级名称自动转换为城市编码
- ✅ **时区支持** - 可选的时区时间参数
- ✅ **详细天气信息** - 包含温度、湿度、风向、风力等完整信息
- ✅ **错误处理** - 完善的错误提示和异常处理

## 📋 系统要求

- Node.js 16.0 或更高版本
- TypeScript 5.0 或更高版本
- 高德地图API密钥

## 🚀 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 构建项目

```bash
npm run build
```

### 3. 运行服务器

```bash
npm start
```

或者开发模式：

```bash
npm run dev
```

## 🔑 获取高德地图API密钥

1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册并登录账号
3. 进入控制台 → 应用管理 → 我的应用
4. 创建新应用，选择「Web服务」类型
5. 获取API Key

## 🛠️ 工具使用说明

### get-weather-forecast

获取指定城市的天气信息。

#### 参数说明

| 参数名 | 类型 | 必选 | 说明 | 示例 |
|--------|------|------|------|------|
| `cityName` | string | ✅ | 中国市级名称 | `"北京市"`, `"上海市"`, `"广州市"` |
| `date` | string | ❌ | 查询日期 (YYYY-MM-DD) | `"2024-01-15"` (默认当天) |
| `forecastType` | string | ❌ | 查询类型 | `"current"` (实时) 或 `"forecast"` (预报) |

#### API密钥配置

本服务器从环境变量 `AMAP_API_KEY` 中读取高德地图API密钥，无需在调用时传递。请确保在启动服务器前设置此环境变量。

#### 使用示例

**实时天气查询：**
```json
{
  "cityName": "北京市",
  "forecastType": "current"
}
```

**天气预报查询：**
```json
{
  "cityName": "广州市",
  "date": "2024-01-15",
  "forecastType": "forecast"
}
```

#### mcp-server 配置示例

```json
{
  "mcpServers": {
    "weather-forecast": {
      "command": "node",
      "args": [
        "/path/to/your/build/index.js"
      ],
      "env": {
        "AMAP_API_KEY": "your_gaode_api_key_here"
      }
    }
  }
}
```

#### 返回示例

**实时天气：**
```
🌈 天气查询结果

📍 北京 北京市
🌤️  天气：晴
🌡️  温度：15°C
💨 风向：西北风
🌪️  风力：3级
💧 湿度：45%
⏰ 更新时间：2024-01-15 14:30:00

📅 查询日期: 2024-01-15
```

**天气预报：**
```
🌈 天气查询结果

📍 上海 上海市

📅 未来几天天气预报：

今天 (星期一)
🌤️  白天：晴 | 夜间：多云
🌡️  温度：8°C ~ 18°C
💨 风向：东北风 3级 | 东风 2级

2024-01-16 (星期二)
🌤️  白天：多云 | 夜间：阴
🌡️  温度：10°C ~ 20°C
💨 风向：东风 2级 | 东南风 1级

📅 查询日期: 2024-01-15
```

## 🏗️ 项目结构

```
mcp-weather-server/
├── src/
│   └── index.ts          # 主服务器代码
├── build/                # 编译输出目录
├── package.json          # 项目配置
├── tsconfig.json         # TypeScript配置
└── README.md            # 项目文档
```

## 🔧 开发说明

### 核心组件

1. **地理编码模块** (`getCityCode`)
   - 将城市名称转换为高德地图城市编码
   - 支持模糊匹配和智能识别

2. **天气查询模块** (`getWeatherInfo`)
   - 调用高德天气API获取天气数据
   - 支持实时天气和预报天气两种模式

3. **数据格式化模块**
   - `formatLiveWeather`: 格式化实时天气数据
   - `formatForecastWeather`: 格式化预报天气数据

### API接口说明

#### 高德地理编码API
- **接口地址**: `https://restapi.amap.com/v3/geocode/geo`
- **功能**: 将地址转换为坐标和城市编码
- **文档**: [地理编码API文档](https://lbs.amap.com/api/webservice/guide/api/georegeo)

#### 高德天气查询API
- **接口地址**: `https://restapi.amap.com/v3/weather/weatherInfo`
- **功能**: 根据城市编码获取天气信息
- **文档**: [天气查询API文档](https://lbs.amap.com/api/webservice/guide/api/weatherinfo)

## ⚠️ 注意事项

1. **API限制**: 高德地图个人开发者账号每日调用限制为5000次
2. **城市名称**: 请使用标准的中国市级名称，如"北京市"而不是"北京"
3. **网络环境**: 确保服务器能够访问高德地图API服务
4. **密钥安全**: 请妥善保管API密钥，避免泄露

## 🐛 故障排除

### 常见错误

1. **"无法找到城市编码"**
   - 检查城市名称拼写是否正确
   - 确认使用的是标准市级名称

2. **"API密钥无效"**
   - 验证API密钥是否正确
   - 确认密钥对应的服务类型为"Web服务"

3. **"网络请求失败"**
   - 检查网络连接
   - 确认防火墙设置允许访问高德API

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

## 📞 支持

如有问题，请通过以下方式联系：
- 提交GitHub Issue
- 查看[高德地图API文档](https://lbs.amap.com/api/webservice/summary)
- 参考[MCP协议文档](https://modelcontextprotocol.io/)