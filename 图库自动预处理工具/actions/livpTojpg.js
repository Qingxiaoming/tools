// livpTojpg.js
// 将 .livp 文件转换为 .jpg 文件
// 使用 WinRAR 和 ImageMagick 进行转换
// 需要将 WinRAR 和 ImageMagick 加入 PATH 环境变量
// 需要将 rar.exe 和 magick.exe 加入 PATH 环境变量
// 需要将 WinRAR 和 ImageMagick 加入 PATH 环境变量

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 工具路径（请根据实际安装位置调整）
const RAR = `"${process.env['ProgramFiles']}\\WinRAR\\WinRAR.exe"`;
const MAGICK = 'magick';   // 已加入 PATH 即可

module.exports = function (filePath) {
  // 只处理 .livp
  if (path.extname(filePath).toLowerCase() !== '.livp') return;

  const dir   = path.dirname(filePath);
  const name  = path.basename(filePath, '.livp');
  const outDir = dir;                       // 与原文件同级
  const tempDir = path.join(outDir, `${name}_temp`);

  try {
    // 1. 创建临时目录
    if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir, { recursive: true });

    // 2. 解压
    execSync(`${RAR} x "${filePath}" "${tempDir}" -ibck -o+`, { stdio: 'pipe' });

    // 3. 找到所有 .heic
    const heics = fs.readdirSync(tempDir).filter(f => /\.heic$/i.test(f));
    if (heics.length === 0) {
      console.log(`No .heic found in ${filePath}`);
      return;
    }

    // 4. 逐张转 jpg
    heics.forEach(h => {
      const heicPath = path.join(tempDir, h);
      const jpgName  = `${path.basename(h, '.heic')}.jpg`;
      const jpgPath  = path.join(outDir, `${name}_${jpgName}`);
      execSync(`"${MAGICK}" "${heicPath}" "${jpgPath}"`, { stdio: 'pipe' });
      console.log(`Converted: ${h} -> ${jpgPath}`);
    });
  } catch (err) {
    console.error(`livpToJpg error on ${filePath}: ${err.message}`);
  } finally {
    // 5. 清理临时目录
    if (fs.existsSync(tempDir)) fs.rmSync(tempDir, { recursive: true, force: true });
  }
};