const { BASE_URL } = require('../../config.js')
const app = getApp()

Page({
  data: { portfolio: '', symbols: '600519.SH,000001.SZ' },

  onPortfolio(e) { this.setData({ portfolio: e.detail.value }) },
  onSymbols(e) { this.setData({ symbols: e.detail.value }) },

  importPortfolio() {
    const items = this.data.portfolio.split('\n').filter(Boolean).map((l) => {
      const [symbol, name] = l.split(',')
      return { symbol: (symbol || '').trim(), name: (name || '').trim() }
    })
    if (!items.length) { wx.showToast({ title: '请填写持仓', icon: 'none' }); return }
    wx.request({
      url: `${BASE_URL}/api/portfolio/import`, method: 'POST',
      header: { 'X-Openid': app.globalData.openid }, data: items,
      success: () => wx.showToast({ title: '已导入持仓' }),
    })
  },

  setWatch() {
    const syms = this.data.symbols.split(/[,\s]+/).filter(Boolean)
    wx.request({
      url: `${BASE_URL}/api/watch`, method: 'POST',
      header: { 'X-Openid': app.globalData.openid }, data: { symbols: syms },
      success: () => wx.showToast({ title: '已订阅异动' }),
    })
  },

  authSub() {
    wx.request({
      url: `${BASE_URL}/api/subscription?scene=close&authorized=true`, method: 'POST',
      header: { 'X-Openid': app.globalData.openid },
      success: () => wx.showToast({ title: '已授权收盘推送' }),
    })
  },
})
