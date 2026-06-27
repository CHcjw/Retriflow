#!/usr/bin/env node
/**
 * MCP Weather Server - 基于高德地图API的天气预报服务
 *
 * 功能说明：
 * - 提供获取天气预报的工具
 * - 使用高德API获取天气信息
 * - 支持中国市级名称查询
 * - 支持指定日期查询（可选）
 *
 * API说明：
 * - 地理编码API：将城市名称转换为citycode
 * - 天气查询API：根据citycode获取天气信息
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
// 高德API基础配置
const AMAP_BASE_URL = "https://restapi.amap.com";
const GEOCODE_API = "/v3/geocode/geo";
const WEATHER_API = "/v3/weather/weatherInfo";
// 创建MCP服务器实例
const server = new McpServer({
    name: "amap-weather-server",
    version: "1.0.0",
});
/**
 * 地理编码接口 - 将城市名称转换为citycode
 * @param address 城市名称（如：北京市、上海市）
 * @param key 高德API密钥
 * @returns Promise<string | null> 返回citycode或null
 */
async function getCityCode(address, key) {
    try {
        const url = `${AMAP_BASE_URL}${GEOCODE_API}?address=${encodeURIComponent(address)}&key=${key}&output=json`;
        const response = await fetch(url);
        const data = await response.json();
        if (data.status === "1" && data.geocodes && data.geocodes.length > 0) {
            // 优先返回adcode，如果没有则返回citycode
            return data.geocodes[0].adcode || data.geocodes[0].citycode || null;
        }
        return null;
    }
    catch (error) {
        console.error("获取城市编码失败:", error);
        return null;
    }
}
/**
 * 天气查询接口 - 根据citycode获取天气信息
 * @param cityCode 城市编码
 * @param key 高德API密钥
 * @param extensions 查询类型：base(实时天气) 或 all(预报天气)
 * @returns Promise<any> 天气数据
 */
async function getWeatherInfo(cityCode, key, extensions = "base") {
    try {
        const url = `${AMAP_BASE_URL}${WEATHER_API}?city=${cityCode}&key=${key}&extensions=${extensions}&output=json`;
        const response = await fetch(url);
        const data = await response.json();
        if (data.status === "1") {
            return data;
        }
        throw new Error(`天气查询失败: ${data.info || '未知错误'}`);
    }
    catch (error) {
        console.error("获取天气信息失败:", error);
        throw error;
    }
}
/**
 * 格式化实时天气信息
 * @param weatherData 天气数据
 * @returns string 格式化后的天气信息
 */
function formatLiveWeather(weatherData) {
    if (!weatherData.lives || weatherData.lives.length === 0) {
        return "暂无实时天气数据";
    }
    const live = weatherData.lives[0];
    return `📍 ${live.province} ${live.city}\n` +
        `🌤️  天气：${live.weather}\n` +
        `🌡️  温度：${live.temperature}°C\n` +
        `💨 风向：${live.winddirection}\n` +
        `🌪️  风力：${live.windpower}级\n` +
        `💧 湿度：${live.humidity}%\n` +
        `⏰ 更新时间：${live.reporttime}`;
}
/**
 * 格式化预报天气信息
 * @param weatherData 天气数据
 * @returns string 格式化后的天气信息
 */
function formatForecastWeather(weatherData) {
    if (!weatherData.forecasts || weatherData.forecasts.length === 0) {
        return "暂无预报天气数据";
    }
    const forecast = weatherData.forecasts[0];
    let result = `📍 ${forecast.province} ${forecast.city}\n\n`;
    if (forecast.casts && forecast.casts.length > 0) {
        result += "📅 未来几天天气预报：\n\n";
        forecast.casts.forEach((cast, index) => {
            result += `${index === 0 ? '今天' : cast.date} (${cast.week})\n`;
            result += `🌤️  白天：${cast.dayweather} | 夜间：${cast.nightweather}\n`;
            result += `🌡️  温度：${cast.nighttemp}°C ~ ${cast.daytemp}°C\n`;
            result += `💨 风向：${cast.daywind} ${cast.daypower}级 | ${cast.nightwind} ${cast.nightpower}级\n\n`;
        });
    }
    return result.trim();
}
/**
 * 获取当前日期的字符串表示
 * @param timezone 时区（可选）
 * @returns string 日期字符串
 */
function getCurrentDateString(timezone) {
    const now = new Date();
    if (timezone) {
        try {
            return new Intl.DateTimeFormat('zh-CN', {
                timeZone: timezone,
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
            }).format(now);
        }
        catch (error) {
            console.warn(`无效的时区: ${timezone}，使用默认时区`);
        }
    }
    return now.toLocaleDateString('zh-CN');
}
// 注册天气查询工具
server.tool("get-weather-forecast", {
    cityName: z.string().describe("中国市级名称，如：北京市、上海市、广州市（必选）"),
    date: z.string().optional().describe("查询日期，格式：YYYY-MM-DD（可选，默认为当天）"),
    forecastType: z.enum(["current", "forecast"]).optional().default("current").describe("查询类型：current(实时天气) 或 forecast(预报天气)，默认为current")
}, async ({ cityName, date, forecastType = "current" }) => {
    try {
        // 从环境变量获取API密钥
        const apiKey = process.env.AMAP_API_KEY;
        if (!apiKey || apiKey.trim() === "") {
            return {
                content: [{
                        type: "text",
                        text: "❌ 错误：未配置高德地图API密钥，请在环境变量AMAP_API_KEY中设置"
                    }]
            };
        }
        // 验证城市名称
        if (!cityName || cityName.trim() === "") {
            return {
                content: [{
                        type: "text",
                        text: "❌ 错误：请提供有效的城市名称"
                    }]
            };
        }
        // 获取城市编码
        console.log(`正在查询城市编码: ${cityName}`);
        const cityCode = await getCityCode(cityName, apiKey);
        if (!cityCode) {
            return {
                content: [{
                        type: "text",
                        text: `❌ 错误：无法找到城市 "${cityName}" 的编码，请检查城市名称是否正确`
                    }]
            };
        }
        console.log(`城市编码获取成功: ${cityCode}`);
        // 根据查询类型设置extensions参数
        const extensions = forecastType === "forecast" ? "all" : "base";
        // 获取天气信息
        console.log(`正在查询天气信息，类型: ${forecastType}`);
        const weatherData = await getWeatherInfo(cityCode, apiKey, extensions);
        // 格式化天气信息
        let formattedWeather;
        if (forecastType === "forecast") {
            formattedWeather = formatForecastWeather(weatherData);
        }
        else {
            formattedWeather = formatLiveWeather(weatherData);
        }
        // 添加查询时间信息
        const queryDate = date || getCurrentDateString();
        const result = `🌈 天气查询结果\n\n${formattedWeather}\n\n📅 查询日期: ${queryDate}`;
        return {
            content: [{
                    type: "text",
                    text: result
                }]
        };
    }
    catch (error) {
        console.error("天气查询失败:", error);
        return {
            content: [{
                    type: "text",
                    text: `❌ 天气查询失败: ${error instanceof Error ? error.message : '未知错误'}`
                }]
        };
    }
});
// 连接服务器到标准输入/输出传输
const transport = new StdioServerTransport();
server.connect(transport);
console.log("🌤️  MCP 天气预报服务器已启动，等待连接...");
console.log("📋 支持的功能:");
console.log("   - 实时天气查询");
console.log("   - 天气预报查询");
console.log("   - 基于高德地图API");
console.log("🔑 使用前请确保已获取高德地图API密钥");
//# sourceMappingURL=index.js.map