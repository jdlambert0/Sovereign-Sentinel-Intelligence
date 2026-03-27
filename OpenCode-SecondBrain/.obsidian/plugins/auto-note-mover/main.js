// Auto Note Mover plugin (enhanced scaffold)
const fs = require('fs')
const path = require('path')

module.exports = class AutoNoteMover {
  constructor() {
    this.app = null
  }
  onload() {
    console.log('[AutoNoteMover] loaded (enhanced scaffold)')
    // In a real Obsidian environment you would hook into vault events, for example:
    // this.registerEvent(this.app.vault.on('create', (file) => this.handleFile(file)))
    // this.registerEvent(this.app.vault.on('modify', (file) => this.handleFile(file)))
  }
  async handleFile(file) {
    if (!file || !file.path) return
    try {
      await this.moveNoteIfTagged(file.path)
    } catch (e) {
      console.error('[AutoNoteMover] handleFile error', e)
    }
  }
  async moveNoteIfTagged(notePath) {
    // Read content and extract frontmatter tags
    if (!fs.existsSync(notePath)) return false
    const content = fs.readFileSync(notePath, 'utf8')
    const fmMatch = content.match(/^---\n([\s\S]*?)\n---/m)
    let tags = []
    if (fmMatch) {
      const fm = fmMatch[1]
      const tagMatch = fm.match(/tags:\s*\[(.*?)\]/)
      if (tagMatch) {
        const inner = tagMatch[1]
        tags = inner.split(',').map(t => t.trim())
      }
    }
    let destDir = null
    if (tags.includes('#session-log')) destDir = path.resolve(notePath, '../../Sessions')
    else if (tags.includes('#topic-note')) destDir = path.resolve(notePath, '../../Topics')
    else if (tags.includes('#research')) destDir = path.resolve(notePath, '../../Resources')
    if (!destDir) return false
    if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true })
    const fileName = path.basename(notePath)
    const destPath = path.join(destDir, fileName)
    if (path.resolve(notePath) === path.resolve(destPath)) return true
    fs.renameSync(notePath, destPath)
    console.log(`[AutoNoteMover] moved ${notePath} -> ${destPath}`)
    return true
  }
  onunload() {
    console.log('[AutoNoteMover] unloaded')
  }
}
