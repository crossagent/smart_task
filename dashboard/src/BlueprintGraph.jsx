import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import mermaid from 'mermaid'
import { RefreshCcw, Info, CheckCircle, XCircle, Search, FileText, Play, Pause, FastForward, Send, Radio } from 'lucide-react'
import EventTimeline from './EventTimeline'

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
  const [systemStatus, setSystemStatus] = useState({ run_mode: 'auto', step_count: 0 })
  const [userInstruction, setUserInstruction] = useState("")
  const mermaidRef = useRef(null)

  const fetchSystemStatus = async () => {
    try {
      const resp = await axios.get('/api/system/status')
      setSystemStatus(resp.data)
    } catch (e) { console.error("Failed to fetch system status", e) }
  }

  const handleSystemControl = async (mode, step = 0) => {
    try {
      await axios.post(`/api/system/control?mode=${mode}&step=${step}`)
      fetchSystemStatus()
    } catch (e) { console.error("System control failed", e) }
  }

  const handleSubmitInstruction = async () => {
    if (!userInstruction.trim()) return
    try {
      await axios.post(`/api/activity/${activityId}/instruction`, { instruction: userInstruction })
      alert("Instruction dispatched to Project Manager!")
      setUserInstruction("")
      fetchSystemStatus()
      fetchGraph()
    } catch (e) { console.error("Failed to submit instruction", e) }
  }

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
    // Check if mermaid is available from import or global
    const m = mermaid || window.mermaid
    if (graphData.nodes.length === 0 || !m) {
      console.warn("Mermaid not available or no nodes to render")
      return
    }
    
    // Generate Mermaid Syntax
    let code = "graph TD\n"
    
    // All nodes rendered uniformly (events are in EventTimeline now, not in graph)
    graphData.nodes.forEach(node => {
      let style = ""
      if (node.status === 'awaiting_approval') {
        style = ":::awaiting"
      } else if (node.status === 'done' || node.status === 'code_done') {
        style = ":::done"
      } else if (node.status === 'ready' || node.status === 'in_progress' || node.status === 'active') {
        style = ":::ready"
      } else if (node.status === 'blocked' || node.status === 'failed') {
        style = ":::blocked"
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
    code += `  classDef blocked fill:#ef4444,stroke:#dc2626,stroke-width:2px,color:#fff\n`
    
    try {
       // Unique ID for SVG generation to avoid collisions
       const { svg } = await m.render('blueprint-svg-' + Date.now(), code)
       if (mermaidRef.current) {
         mermaidRef.current.innerHTML = svg
         
         // Attach click listeners to SVG nodes
         const nodes = mermaidRef.current.querySelectorAll('.node')
         nodes.forEach(nodeEl => {
           nodeEl.style.cursor = 'pointer'
           nodeEl.onclick = () => {
             // Extract task ID from the element ID or classes
             // Mermaid node IDs often look like "task-ID" or just "ID"
             const possibleIds = Array.from(nodeEl.classList).concat([nodeEl.id])
             const nodeId = graphData.nodes.find(n => nodeEl.id.includes(n.id))?.id
             if (nodeId) {
                const task = graphData.nodes.find(n => n.id === nodeId)
                if (task) setSelectedTask(task)
             }
           }
         })
       }
    } catch (e) {
      console.error("Mermaid Render Error", e)
    }
  }

  useEffect(() => {
    fetchGraph()
    fetchSystemStatus()
    const interval = setInterval(fetchSystemStatus, 5000)
    return () => clearInterval(interval)
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
      {/* Tool Bar & Cockpit */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-bold text-slate-400">BLUEPRINT TOPOLOGY</h2>
            <div className={`flex items-center gap-3 px-3 py-1.5 rounded-full text-[10px] font-bold tracking-widest border transition-all duration-500 ${
              systemStatus.run_mode === 'auto' 
                ? 'bg-green-500/10 text-green-500 border-green-500/20 shadow-[0_0_15px_rgba(34,197,94,0.1)]' 
                : 'bg-amber-500/10 text-amber-500 border-amber-500/20 shadow-[0_0_15px_rgba(245,158,11,0.1)]'
            }`}>
              <Radio size={12} className={systemStatus.run_mode === 'auto' ? 'animate-pulse' : ''} />
              {systemStatus.run_mode === 'auto' ? 'AUTONOMOUS / LIVE' : 'MANUAL / PAUSED'}
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Contextual Controller */}
            <div className="flex items-center bg-slate-900 border border-slate-700/50 rounded-xl p-1 shadow-2xl">
               
               {/* PRIMARY TOGGLE: Auto <-> Pause */}
               <button 
                onClick={() => handleSystemControl(systemStatus.run_mode === 'auto' ? 'pause' : 'auto')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-xs uppercase tracking-tighter transition-all duration-300 ${
                  systemStatus.run_mode === 'auto' 
                    ? 'text-amber-400 hover:bg-amber-500/10 hover:text-amber-300' 
                    : 'bg-green-600 text-white hover:bg-green-500 shadow-lg shadow-green-900/20'
                }`}
               >
                 {systemStatus.run_mode === 'auto' ? (
                   <><Pause size={16} fill="currentColor" /> Pause Bus</>
                 ) : (
                   <><Play size={16} fill="currentColor" /> Resume Auto</>
                 )}
               </button>

               {/* CONDITIONAL STEP: Only show when paused */}
               {systemStatus.run_mode === 'pause' && (
                 <button 
                  onClick={() => handleSystemControl('pause', 1)}
                  className="flex items-center gap-2 ml-1 px-4 py-2 text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-all animate-in fade-in slide-in-from-left-2 duration-300 border border-transparent hover:border-slate-700"
                  title="Execute Single 5s Cycle"
                 >
                   <FastForward size={16} fill="currentColor" />
                   <span className="text-[10px] font-bold uppercase tracking-widest">Next Turn</span>
                 </button>
               )}

               <div className="h-6 w-[1px] bg-slate-700/50 mx-2" />
               
               {/* BROADCAST FIELD */}
               <div className="flex items-center px-4 bg-slate-950/30 rounded-lg border border-transparent focus-within:border-slate-600 transition-all">
                  <span className="text-slate-600 font-mono text-[10px] mr-2">{"CMD>"}</span>
                  <input 
                    type="text" 
                    placeholder="Broadcast instruction to PM..."
                    value={userInstruction}
                    onChange={(e) => setUserInstruction(e.target.value)}
                    className="bg-transparent border-none text-xs focus:ring-0 w-64 text-slate-100 placeholder:text-slate-600 font-medium py-2"
                    onKeyDown={(e) => e.key === 'Enter' && handleSubmitInstruction()}
                  />
                  <button 
                    onClick={handleSubmitInstruction}
                    className="ml-2 p-2 text-brand-blue hover:text-white transition-all hover:scale-110 active:scale-95"
                  >
                    <Send size={16} />
                  </button>
               </div>
            </div>

            <button 
              onClick={fetchGraph}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-3 bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-700 transition-all text-sm font-bold shadow-lg"
            >
              <RefreshCcw size={16} className={`${loading ? 'animate-spin' : ''}`} />
              Sync
            </button>
          </div>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="glass-panel min-h-[500px] flex items-center justify-center overflow-auto p-12">
        <div ref={mermaidRef} id="graphDiv" className="w-full flex justify-center" />
      </div>

      {/* Event Timeline */}
      <EventTimeline activityId={activityId} />

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
