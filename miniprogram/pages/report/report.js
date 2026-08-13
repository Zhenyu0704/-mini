const { BASE_URL } = require('../../config.js')

Page({
  data: { task_id: '', html_url: '', summary: null, status: '' },

  onLoad(opt) {
    const task_id = opt.task_id || ''
    this.setData({ task_id })
    this.load(task_id)
  },

  load(task_id) {
    wx.request({
      url: `${BASE_URL}/api/roundtable/${task_id}`,
      success: (res) => {
        const d = res.data || {}
        this.setData({ status: d.status, html_url: d.report_html_url, summary: d.summary })
        if (d.status && d.status !== 'done') {
          setTimeout(() => this.load(task_id), 2000)
        }
      },
    })
  },
})
