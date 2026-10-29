// 把 src/**/*.ts 镜像到临时目录，把相对 import 补上 .ts 后缀，好让 node --experimental-strip-types 直接跑真模块
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync, rmSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'

const SRC = 'work/frontend/ui-vue/src'
const OUT = 'work/verify/.tmp/src'
rmSync('work/verify/.tmp', { recursive: true, force: true })

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (name.endsWith('.ts')) out.push(p)
  }
  return out
}

for (const file of walk(SRC)) {
  const rel = relative(SRC, file)
  const dest = join(OUT, rel)
  mkdirSync(dirname(dest), { recursive: true })
  let code = readFileSync(file, 'utf8')
  code = code.replace(/(from\s+')(\.{1,2}\/[^']*?)(')/g, (m, a, spec, c) => {
    if (/\.(ts|js|json|vue)$/.test(spec)) return m
    return `${a}${spec}.ts${c}`
  })
  writeFileSync(dest, code)
}
console.log(`mirrored ${walk(SRC).length} .ts files → ${OUT}`)
