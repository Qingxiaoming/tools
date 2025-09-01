// renameToDate.js
// 将文件重命名为日期格式
// 使用创建时间作为日期前缀
// 需要将文件名长度限制在260字符以内

const fs = require('fs');
const path = require('path');

// 检测是否已带日期前缀
const DATE_PREFIX_RE = /^(\d{6}_\d{6})_/;
const MAX_SAFE_LEN   = 230; // 留出 30 字符给日期前缀和扩展名

module.exports = function (filePath) {
  const dir   = path.dirname(filePath);
  const ext   = path.extname(filePath);
  let   name  = path.basename(filePath, ext);

  // 如果已重命名，直接跳过
  if (DATE_PREFIX_RE.test(name)) return;

  // 取创建时间
  const birth = fs.statSync(filePath).birthtime;
  const stamp = birth.toISOString()
                     .replace(/[-:]/g, '')
                     .slice(2, 15)          // 250816T101431
                     .replace('T', '_');    // 250816_101431

  // 截断原始文件名，确保总长度<260
  const maxNameLen = MAX_SAFE_LEN - stamp.length - ext.length - 1;
  const safeName   = name.length > maxNameLen ? name.slice(0, maxNameLen) : name;

  const newName = `${stamp}_${safeName}${ext}`;
  const newPath = path.join(dir, newName);

  // 超长保护：若仍超限，直接跳过
  if (newPath.length >= 260) {
    console.warn(`Skip: path too long – ${filePath}`);
    return;
  }

  try {
    fs.renameSync(filePath, newPath);
    console.log(`Renamed: ${name}${ext} -> ${newName}`);
  } catch (err) {
    console.error(`Failed to rename ${filePath}: ${err.message}`);
  }
};