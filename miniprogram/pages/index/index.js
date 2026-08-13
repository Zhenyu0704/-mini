const { BASE_URL } = require('../../config.js')

Page({
  data: { query: '', type: 'single', symbols: '', loading: false },

  onType(e) { this.setData({ type: e.currentTarget.dataset.t }) },
  onInput(e) { this.setData({ query: e.detail.value }) },
  onSymbols(e) { this.setData({ symbols: e.detail.value }) },

  submit() {
    const { query, type, symbols } = this.data
    if (!query) { wx.showToast({ title: '请输入问题', icon: 'none' }); return }
    const symList = symbols ? symbols.split(/[,\s]+/).filter(Boolean) : []
    this.setData({ loading: true })
    wx.request({
      url: `${BASE_URL}/api/roundtable`,
      method: 'POST',
      data: { query, type, symbols: symList },
      success: (res) => {
        if (res.data && res.data.task_id) this.poll(res.data.task_id)
        else { this.setData({ loading: false }); wx.showToast({ title: '发起失败', icon: 'none' }) }
      },
      fail: () => { this.setData({ loading: false }); wx.showToast({ title: '网络错误', icon: 'none' }) },
    })
  },

  poll(task_id) {
    const timer = setInterval(() => {
      wx.request({
        url: `${BASE_URL}/api/roundtable/${task_id}`,
        success: (res) => {
          const st = res.data && res.data.status
          if (st === 'done') {
            clearInterval(timer); this.setData({ loading: false })
            wx.navigateTo({ url: `/pages/report/report?task_id=${task_id}` })
          } else if (st === 'interrupted' || st === 'not_found') {
            clearInterval(timer); this.setData({ loading: false })
            wx.showToast({ title: '生成失败', icon: 'none' })
          }
        },
      })
    }, 2000)
  },
})
