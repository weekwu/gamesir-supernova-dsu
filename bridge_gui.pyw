"""Small local start/stop window for the tested Supernova DSU bridge."""
import json, pathlib, subprocess, sys, tempfile, time, tkinter as tk
from tkinter import ttk
from supernova_dsu import DEFAULT_OPTIONS, read_options

folder=pathlib.Path(__file__).resolve().parent
runtime=pathlib.Path(tempfile.mkdtemp(prefix='GameSir-DSU-'))
status_path=runtime/'status.json'
log_path=runtime/'bridge.log'
options_path=folder/'settings.json'
preview='--preview' in sys.argv
proc=None
log=None
root=tk.Tk();root.title('超新星 · Cemu 无线体感'+(' · 界面预览' if preview else ''));root.geometry('550x590');root.resizable(False,False)
ttk.Label(root,text='2.4GHz Switch 模式 → Cemu 体感',font=('Microsoft YaHei UI',14)).pack(pady=(18,10))
ttk.Label(root,text='先开启体感桥，再打开 Cemu。保持此窗口打开。').pack()
state=tk.StringVar(value='准备就绪');details=tk.StringVar(value='本机连接：127.0.0.1:26761')
ttk.Label(root,textvariable=state,font=('Microsoft YaHei UI',12)).pack(pady=(15,5))
ttk.Label(root,textvariable=details).pack()
ttk.Label(root,text='Cemu：Wii U GamePad / GameSir_24G_DSU\nBetterJoy 请保持关闭。Steam 可以开启。',justify='center').pack(pady=10)

options=read_options(options_path)
mode_names={'本机 Cemu 标准换算':'cemu26','之前的校准换算':'calibrated'}
mode=tk.StringVar(value=next(k for k,v in mode_names.items() if v==options['mode']))
gain=tk.DoubleVar(value=options['gain'])
smoothing=tk.DoubleVar(value=options['smoothing_ms'])
deadzone=tk.DoubleVar(value=options['deadzone_dps'])
controls=ttk.LabelFrame(root,text='体感手感');controls.pack(fill='x',padx=20,pady=8)
ttk.Label(controls,text='换算方案').grid(row=0,column=0,padx=10,pady=8,sticky='w')
ttk.Combobox(controls,textvariable=mode,values=list(mode_names),state='readonly',width=25).grid(row=0,column=1,columnspan=2,sticky='w')
for row,label,var,lo,hi,fmt in [(1,'灵敏度倍率',gain,.5,2,'{:.2f}×'),(2,'平滑',smoothing,0,100,'{:.0f} 毫秒'),(3,'体感死区',deadzone,0,2,'{:.2f} °/秒')]:
    ttk.Label(controls,text=label).grid(row=row,column=0,padx=10,pady=10,sticky='w')
    ttk.Scale(controls,variable=var,from_=lo,to=hi,length=240).grid(row=row,column=1)
    value_label=tk.StringVar(value=fmt.format(var.get()))
    var.trace_add('write',lambda *_,v=var,t=value_label,f=fmt:t.set(f.format(v.get())))
    ttk.Label(controls,textvariable=value_label,width=13).grid(row=row,column=2,padx=8)
ttk.Label(controls,text='平滑越高越稳，也会更滞后；死区越大越容易忽略微小动作。').grid(row=4,column=0,columnspan=3,pady=(4,7))
ttk.Label(root,text='默认按已测试的 Cemu 2.6 换算 / 1.00× / 平滑和死区关闭\n运行时调整会直接生效，无需重启 Cemu。',justify='center').pack(pady=4)
save_timer=None
def save_options():
    global save_timer
    save_timer=None
    values=dict(mode=mode_names[mode.get()],gain=round(gain.get(),3),smoothing_ms=round(smoothing.get(),1),deadzone_dps=round(deadzone.get(),3))
    temporary=options_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(values,indent=2,ensure_ascii=False),encoding='utf8')
    temporary.replace(options_path)
def schedule_save(*_):
    global save_timer
    if save_timer:root.after_cancel(save_timer)
    save_timer=root.after(150,save_options)
for var in (mode,gain,smoothing,deadzone):var.trace_add('write',schedule_save)
def reset_options():
    mode.set('本机 Cemu 标准换算');gain.set(1);smoothing.set(0);deadzone.set(0)
ttk.Button(root,text='恢复标准默认值',command=reset_options).pack(pady=5)

def start():
    global proc,log
    if preview:state.set('界面预览 · 未连接手柄');return
    if proc and proc.poll() is None:return
    save_options()
    log=log_path.open('a',encoding='utf8')
    proc=subprocess.Popen([sys.executable,'-u',str(folder/'supernova_dsu.py'),'--initialize','--status',str(status_path),'--options-file',str(options_path)],cwd=folder,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    state.set('正在连接手柄…')
def stop():
    global proc,log
    if proc and proc.poll() is None:
        proc.terminate();proc.wait(timeout=3)
    if log:log.close();log=None
    proc=None;state.set('已停止');details.set('关闭此窗口即可退出体感桥')
def refresh():
    if proc:
        if proc.poll() is not None:
            state.set('未能启动 / 连接已中断')
            try:
                error=log_path.read_text(encoding='utf8')[-1600:]
                if '10048' in error:details.set('已有体感桥在运行，请先关闭另一个体感桥')
                elif 'found 0' in error:details.set('请连接接收器，并将手柄切到 Switch 模式后重试')
                else:details.set('请关闭 BetterJoy，再点击“开始”；详细日志保存在临时目录')
            except OSError:pass
        elif status_path.exists():
            try:
                s=json.loads(status_path.read_text(encoding='utf8'))
                age=s.get('report_age')
                fresh=time.time()-status_path.stat().st_mtime<2
                if not fresh or age is None or age>1:state.set('等待手柄体感数据…')
                else:state.set('体感数据正常 · Cemu 已接入' if s['clients'] else '体感数据正常 · 等待 Cemu')
                details.set(f"已读取 {s['reports']:,} 个报告 · 已发送 {s['packets_sent']:,} 个数据包")
            except (OSError,ValueError):pass
    root.after(500,refresh)
buttons=ttk.Frame(root);buttons.pack(pady=4)
ttk.Button(buttons,text='开始 / 重试',command=start).pack(side='left',padx=10)
ttk.Button(buttons,text='停止',command=stop).pack(side='left',padx=10)
root.protocol('WM_DELETE_WINDOW',lambda:(stop(),root.destroy()))
root.after(200,start);refresh();root.mainloop()
