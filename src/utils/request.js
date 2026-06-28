import axios from 'axios'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: 'http://127.0.0.1:5000/api',
  timeout: 20000
})

service.interceptors.response.use(
  res => res.data,
  err => {
    return Promise.reject(err)
  }
)

export default service