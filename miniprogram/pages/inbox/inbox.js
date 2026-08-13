const { BASE_URL } = require('../../config.js')
const app = getApp()

Page({
  data: { list: [] },
  onShow() { this.load() },
  load() {
    wx.request({
      url: `${BASE_URL}/api/inbox`,
      header: { 'X-Openid': app.globalData.openid },
      success: (res) => { this.setData({ list: res.data || [] }) },
    })
  },
  open(e) {
    const tid = e.currentTarget.dataset.tid
    if (tid) wx.navigateTo({ url: `/pages/report/report?task_id=${tid}` })
  },
})
