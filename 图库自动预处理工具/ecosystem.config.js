// ecosystem.config.js
// 用于 PM2 启动文件
// 需要将 PM2 加入 PATH 环境变量

module.exports = {
  apps: [{
    name: 'FileWatcher',
    script: './watcher.js',
    cwd: __dirname,
    env: { NODE_ENV: 'production' }
  }]
};
