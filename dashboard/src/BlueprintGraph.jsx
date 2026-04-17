import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import mermaid from 'mermaid'
import { RefreshCcw, Info, CheckCircle, XCircle, Search, FileText } from 'lucide-react'

// Initialize Mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  themeVariables: {
    primaryColor: '#1e293b',
    primaryTextColor: '#f8fafc',
    primaryBorderColor: '#334155',
    lineColor: '#64748b',
    secondaryColor: '#334155',
    tertiaryColor: '#1e293b'
  }
})

function BlueprintGraph({ activityId }) {
  const [data, setData] = useState({ nodes: [], edges: [] })
  const [selectedTask, setSelectedTask] = useState(null)
  const [loading, setLoading] = useState(false)
  const mermaidRef = useRef(null)

  const fetchGraph = async () => {
    setLoading(true)
    try {
      const resp = await axios.get(`/api/activity/${activityId}/graph`)
      setData(resp.data)
      renderMermaid(resp.data)
    } catch (err) {
      console.error("Graph fetch failed", err)
    }
    setLoading(false)
  }

  const renderMermaid = async (graphData) => {
    if (graphData.nodes.length === 0) return
    
    // Generate Mermaid Syntax
    let code = "graph TD\n"
    
    // Define Nodes with Styling
    graphData.nodes.forEach(node => {
      let style = ""
      if (node.status === 'awaiting_approval') {
        style = ":::awaiting"
      } else if (node.status === 'done' || node.status === 'code_done') {
        style = ":::done"
      } else if (node.status === 'ready') {
        style = ":::ready"
      }
      
      const label = node.label.replace(/\n/g, "<br/>")
      code += `  ${node.id}["${label}"]${style}\n`
    })
    
    // Define Edges
    graphData.edges.forEach(edge => {
      code += `  ${edge.from} --> ${edge.to}\n`
    })
    
    // Custom Classes
    code += `  classDef awaiting fill:#f59e0b,stroke:#fcd34d,stroke-width:2px,color:#fff\n`
    code += `  classDef done fill:#10b981,stroke:#059669,stroke-width:1px,color:#fff\n`
    code += `  classDef ready fill:#3b82f6,stroke:#2563eb,stroke-width:1px,color:#fff\n`
    
    try {
       const { svg } = await mermaid.render('graphDiv', code)
       if (mermaidRef.current) {
         mermaidRef.current.innerHTML = svg
         
         // Attach click listeners to SVG rects (hacky but works for Mermaid)
         const rects = mermaidRef.current.querySelectorAll('.node')
         rects.forEach(rect => {
           rect.style.cursor = 'pointer'
           rect.onclick = () => {
             const taskId = rect.id.split('-')[1] // Mermaid usually formats IDs like task-TSK...
             const task = graphData.nodes.find(n => n.id === taskId)
             if (task) setSelectedTask(task)
           }
         })
       }
    } catch (e) {
      console.error("Mermaid Render Error", e)
    }
  }

  useEffect(() => {
    fetchGraph()
  }, [activityId])

  const handleApprove = async (id) => {
    try {
      await axios.get(`/api/task/${id}/approve`) // Assuming we add this to dashboard_api
      fetchGraph()
      setSelectedTask(null)
    } catch (e) { alert("Approval failed") }
  }

  return (
    <div className="relative flex flex-col gap-6">
      {/* Tool Bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-400">BLUEPRINT TOPOLOGY</h2>
        <button 
          onClick={fetchGraph}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition-all text-sm font-medium"
        >
          <RefreshCcw size={16} className={`${loading ? 'animate-spin' : ''}`} />
          Refresh Blueprint
        </button>
      </div>

      {/* Graph Canvas */}
      <div className="glass-panel min-h-[500px] flex items-center justify-center overflow-auto p-12">
        <div ref={mermaidRef} id="graphDiv" className="w-full flex justify-center" />
      </div>

      {/* Side Detail Panel (Drawer) */}
      {selectedTask && (
        <div className="fixed inset-y-0 right-0 w-[450px] bg-slate-900 border-l border-slate-700 shadow-2xl z-50 flex flex-col transform transition-transform duration-300">
           <div className="p-8 flex-1 overflow-y-auto">
             <div className="flex justify-between items-start mb-8">
               <div>
                 <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest block mb-1">TASK DETAILS</span>
                 <h3 className="text-2xl font-bold italic">{selectedTask.id}</h3>
               </div>
               <button onClick={() => setSelectedTask(null)} className="text-slate-500 hover:text-white">
                 <XCircle size={24} />
               </button>
             </div>

             <div className="space-y-8">
                <section>
                  <h4 className="flex items-center gap-2 text-brand-blue font-bold text-sm mb-3 uppercase tracking-tight">
                    <Search size={16} /> Iteration Goal
                  </h4>
                  <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700 text-sm leading-relaxed text-slate-200 italic">
                    {selectedTask.goal}
                  </div>
                </section>

                <section>
                   <h4 className="flex items-center gap-2 text-slate-400 font-bold text-sm mb-3 uppercase tracking-tight">
                    <FileText size={16} /> Audit Status
                  </h4>
                  <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                     <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                       <span className="text-slate-500 block mb-1 uppercase">State</span>
                       <span className="text-slate-100">{selectedTask.status.toUpperCase()}</span>
                     </div>
                     <div className="bg-slate-800 p-3 rounded-lg border border-slate-700">
                       <span className="text-slate-500 block mb-1 uppercase">Approved</span>
                       <span className={selectedTask.is_approved ? 'text-brand-green' : 'text-brand-red'}>
                         {selectedTask.is_approved ? 'YES' : 'NO'}
                       </span>
                     </div>
                  </div>
                </section>
             </div>
           </div>

           {/* Actions */}
           <div className="p-8 bg-slate-950/50 border-t border-slate-700 flex gap-4">
              {selectedTask.status === 'awaiting_approval' && (
                <button 
                  onClick={() => handleApprove(selectedTask.id)}
                  className="flex-1 bg-brand-green hover:bg-green-600 text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-brand-green/20"
                >
                  <CheckCircle size={20} />
                  APPROVE AND RELEASE
                </button>
              )}
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold py-4 rounded-xl border border-slate-600 transition-all">
                REJECT
              </button>
           </div>
        </div>
      )}
    </div>
  )
}

export default BlueprintGraph
