// watcher.js
// 用于监视指定目录下的文件变化
// 开启log:
// pm2 logs FileWatcher

const chokidar = require('chokidar');
const fs = require('fs');
const path = require('path');

const watchDir = 'D:\\Users\\Windows10\\Desktop\\0V0_燕小重的知识库\\图库\\未分类';
const actionsDir = path.join(__dirname, 'actions');

function runPlugins(file) {
  fs.readdirSync(actionsDir)
    .filter(f => f.endsWith('.js'))
    .forEach(f => require(path.join(actionsDir, f))(file));
}

chokidar.watch(watchDir, { ignored: /(^|[\/\\])\../, persistent: true })
  .on('add', file => setTimeout(() => runPlugins(file), 1000));
