import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Toaster } from '@/components/ui/sonner'
import { QcSetupPage } from '@/pages/qc-setup-page'
import { LauncherPage } from '@/pages/launcher-page'
import { ResultPage } from '@/pages/result-page'
import { TaskRunEntryPage } from '@/pages/task-run-entry-page'

function App() {
  return (
    <>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LauncherPage />} />
          <Route path="/task-runs/:taskRunId/qc-setup" element={<QcSetupPage />} />
          <Route path="/task-runs/:taskRunId/result" element={<ResultPage />} />
          <Route path="/task-runs/:taskRunId" element={<TaskRunEntryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </>
  )
}

export default App
