import sys, glob, os, subprocess, re
from ipywidgets import interact_manual,fixed,Layout,interact, FloatSlider
import ipywidgets as widgets
interact_calc=interact_manual.options(manual_name="Make New Input and Run")
import osiris
from scipy import optimize
import numpy as np
import h5py
import matplotlib.pyplot as plt
    
def newifile(oname='single-part-1',field_solve='yee',dx1=0.2,dx2=0.2,dt=0.95,
            t_final=600.0,pusher='standard',uz0=0.0,a0=1.0,phi0=0.0,nproc=4,run_osiris=True):
    
    if field_solve == 'fei':
        fname = 'single-part-fei.txt'
    else:
        fname = 'single-part-std.txt'

    # Remake the tags file based on the number of processors being used
    with open('tags-single-particle.txt') as osdata:
        data = osdata.readlines()
    data[1] = '{:d}, 1,'.format(nproc//2+1)
    with open('tags-single-particle.txt','w') as f:
        for line in data:
            f.write(line)

    with open(fname) as osdata:
        data = osdata.readlines()

    # Replace all parameters that don't depend on dt
    for i in range(len(data)):
        if 'node_number' in data[i]:
            data[i] = '  node_number(1:2) =  {:d}, 1,\n'.format(nproc)
        if 'nx_p' in data[i]:
            data[i] = '  nx_p(1:2) =  {:d}, 12,\n'.format(np.around(200.0/dx1).astype(int))
        if 'xmin' in data[i]:
            data[i] = '  xmin(1:2) = -100.0, -{:f},\n'.format(6.0*dx2)
        if 'xmax' in data[i]:
            data[i] = '  xmax(1:2) =  100.0,  {:f},\n'.format(6.0*dx2)
        if ' x(1:6,2)' in data[i]:
            data[i] = '  x(1:6,2)  = -1.0, 0.0, {:f}, {:f}, {:f},\n'.format(dx2/2,dx2,dx2*2)
        if 'tmax =' in data[i]:
            data[i] = '  tmax = '+str(t_final)+',\n'
        if 'push_type' in data[i]:
            data[i] = '  push_type = "'+pusher+'",\n'
        if ' a0 =' in data[i]:
            data[i] = '  a0 = '+str(a0)+',\n'
        if 'phase =' in data[i]:
            data[i] = '  phase = '+str(phi0)+',\n'

    with open(oname+'.txt','w') as f:
        for line in data:
            f.write(line)

    # Calculate the courant limit given the above parameters
    # This is done by running OSIRIS with a large timestep and getting the max(dt) value
    if os.path.isfile('osiris-2D.e'):
        os_exec = './osiris-2D.e'
    else:
        os_exec = '/usr/local/osiris/osiris-2D.e'
    output = subprocess.run( [os_exec,"-t",oname+'.txt'], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE )
    courant = float( re.search( r"max\(dt\).*([0-9]+\.[0-9]*)", output.stdout.decode("utf-8") ).group(1) )

    # Generate final input deck with new time step
    for i in range(len(data)):
        if 'dt ' in data[i]:
            data[i] = '  dt     =   '+str(dt*courant)+',\n'
        if 'dtdx1' in data[i]:
            data[i] = '  dtdx1 = '+str(dt*courant/dx1)+', ! dt/dx1\n'
        if 'ufl(1:3)' in data[i]:
            # Give correct initial velocity in x2 since this is the momentum at -dt/2
            # With this momentum, the true initial velocity in x2 will average to 0
            data[i] = '  ufl(1:3) = '+str(uz0)+', '+str( dt*courant*a0/2.0 - 
                np.sqrt( ( np.sqrt( np.square( a0*dt*courant*uz0 )
                                  + np.square( 1.0 + np.square(uz0) ) )
                                  - 1.0 - np.square(uz0) ) / 2.0 ) )+', 0.0,\n'

    with open(oname+'.txt','w') as f:
        for line in data:
            f.write(line)
    
    print('New file '+oname+'.txt is written.')
    if run_osiris:
        print('Running OSIRIS in directory '+oname+'...')
        osiris.runosiris_2d(rundir=oname,inputfile=oname+'.txt',print_out='yes',combine='no',np=nproc)

def single_particle_widget(run_osiris=True,nproc=4):
    style = {'description_width': '350px'}
    layout = Layout(width='55%')

    a = widgets.Text(value='single-part-1', description='New output file:',style=style,layout=layout)
    b = widgets.Dropdown(options=['yee', 'fei'],value='yee', description='Field solver:',style=style,layout=layout)
    c = widgets.BoundedFloatText(value=0.2, min=0.00001, max=3.0, description='dx1:',style=style,layout=layout)
    d = widgets.BoundedFloatText(value=20.0, min=0.00001, max=300.0, description='dx2:',style=style,layout=layout)
    e = widgets.BoundedFloatText(value=0.95, min=0.0, max=0.999, description='dt/t_courant:',style=style,layout=layout)
    f = widgets.BoundedFloatText(value=600.0, min=40.0, max=1e9, description='t_final:',style=style,layout=layout)
    g = widgets.Dropdown(options=['standard', 'vay', 'cond_vay', 'cary', 'fullrot', 'euler'],value='standard',description='Pusher:',style=style,layout=layout)
    h = widgets.FloatText(value=0.0, description='uz0:',style=style,layout=layout)
    i = widgets.BoundedFloatText(value=1.0, min=0, max=1e3, description='a0:',style=style,layout=layout)
    j = widgets.BoundedFloatText(value=0.0, min=-180, max=180, description='phi0 (degrees):',style=style,layout=layout)

    im = interact_calc(newifile, oname=a,field_solve=b,dx1=c,dx2=d,dt=e,t_final=f,pusher=g,uz0=h,a0=i,phi0=j,nproc=fixed(nproc),run_osiris=fixed(run_osiris));
    im.widget.manual_button.layout.width='250px'
    return a

def haines(a0,ux0,uy0,uz0,t0,tf,z0):
    # Parameters
    # Ex = E0 sin(wt - kz)
    # a0 = laser amplitude
    # g0 = initially gamma of the particle
    # u[xyz]0 = normalized initial momenta (i.e., proper velocities, gamma*v)
    # t0 = initial time when the EM-wave hits the particle (can be thought of as phase of laser)
    # z0 = initial position of the particle
    g0 = np.sqrt( 1. + np.square(ux0) + np.square(uy0) + np.square(uz0) )
    bx0=ux0/g0; by0=uy0/g0; bz0=uz0/g0;

    phi0 = t0 - z0
    
    # Solve for the final value of s for the desired final value of time
    def t_haines(s):
        return (1./(2*g0*(1-bz0))*( 0.5*np.square(a0)*s + np.square(a0)/(4*g0*(1-bz0))*
                        ( np.sin(2*g0*(1-bz0)*s+2*phi0) - np.sin(2*phi0) ) + 
                        2*a0*(g0*bx0 - a0*np.cos(phi0))/(g0*(1-bz0))*( np.sin(g0*(1-bz0)*s+phi0) - np.sin(phi0) ) +
                        np.square(g0*bx0 - a0*np.cos(phi0))*s + s + np.square(g0*by0)*s ) - 0.5*g0*(1-bz0)*s + 
                        g0*(1-bz0)*s - tf)
    sf = optimize.root_scalar(t_haines,x0=0,x1=tf).root
    
    s=np.linspace(0,sf,1000)
    x = a0/(g0*(1-bz0)) * ( np.sin( g0*(1-bz0)*s + phi0 ) - np.sin(phi0) ) - a0*s*np.cos(phi0) + g0*bx0*s
    z = 1./(2*g0*(1-bz0))*( 0.5*np.square(a0)*s + np.square(a0)/(4*g0*(1-bz0))*
                        ( np.sin(2*g0*(1-bz0)*s+2*phi0) - np.sin(2*phi0) ) + 
                        2*a0*(g0*bx0 - a0*np.cos(phi0))/(g0*(1-bz0))*( np.sin(g0*(1-bz0)*s+phi0) - np.sin(phi0) ) +
                        np.square(g0*bx0 - a0*np.cos(phi0))*s + s + np.square(g0*by0)*s ) - 0.5*g0*(1-bz0)*s
    t = z + g0*(1-bz0)*s

    px = a0*( np.cos(g0*(1-bz0)*s + phi0) - np.cos(phi0) ) + g0*bx0
    pz = 1./(2*g0*(1-bz0))*( np.square( -a0*(np.cos(g0*(1-bz0)*s + phi0) - np.cos(phi0)) - g0*bx0 ) + 
                            1 + np.square(g0*by0) ) - 0.5*g0*(1-bz0)
    g = np.sqrt(1+np.square(px)+np.square(pz))
    return [t,x,z,px,pz,g]

def grab_data(dirname):
    f=h5py.File(dirname+'/MS/TRACKS/electron-tracks.h5','r')
    t = f['data'][:,0]
    ene = f['data'][:,2]
    x1 = f['data'][:,3]
    x2 = f['data'][:,4]
    p1 = f['data'][:,5]
    p2 = f['data'][:,6]
    i_max = np.argmax(f['data'][:,1]==0) # Find where charge is 0, i.e., particle leaves
    f.close()

    x1 = x1-x1[0]
    x2 = x2-x2[0]

    with open(dirname+'.txt') as osdata:
        data = osdata.readlines()
    for i in range(len(data)):
        if 'xmax(1:2)' in data[i]:
            L_x2 = float(data[i].split(",")[-2])

    # Correct for periodicity jump in x2
    for i in np.arange(len(x2)-1):
        if x2[i+1]-x2[i]>L_x2:
            x2[i+1:] -= 2*L_x2
        elif x2[i+1]-x2[i]<-L_x2:
            x2[i+1:] += 2*L_x2

    return [t,x2,x1,p2,p1,ene,i_max]

def plot_data(dirname,offset=None,theory=True,xlim_max=None,plot_z=False,save_fig=True):
    # Get a0 and uz0 from input deck
    with open(dirname+'.txt') as osdata:
        data = osdata.readlines()
    for i in range(len(data)):
        if 'ufl(1:3)' in data[i]:
            uz0 = float(data[i].split(" ")[-3][:-1])
        if ' a0 =' in data[i]:
            a0 = float(data[i].split(" ")[-1][:-2])
        if 'phase = ' in data[i]:
            off = float(data[i].split(" ")[-1][:-2])*np.pi/180.

    if offset is not None:
        off = offset

    [t,x2,x1,p2,p1,ene,i_max] = grab_data(dirname)
    if xlim_max==None:
        tf = np.max(t)
    else:
        tf = xlim_max
    ux0=0.0; uy0=0.0; t0=np.pi/2-off; z0=0.0;
    [tt,xx,zz,pxx,pzz,gg] = haines(a0,ux0,uy0,uz0,t0,tf,z0)

    if xlim_max==None:
        xlim_max = tf
        l = len(t)
    else:
        if xlim_max >= np.max(t):
            l = len(t)
        else:
            l = np.argmax(t>xlim_max)

    # Don't plot values after the particle has left the box
    if i_max > 0:
        l = np.min([ l, i_max ])

    plt.figure(figsize=(14,6),dpi=300)

    plt.subplot(151)
    if plot_z:
        plt.plot(t[:l],x1[:l],label='simulation')
        if theory: plt.plot(tt,zz,'--',label='theory')
        plt.ylabel('$z$ $[c/\omega_0]$')
    else:
        plt.plot(t[:l],t[:l]-x1[:l],label='simulation')
        if theory: plt.plot(tt,tt-zz,'--',label='theory')
        plt.ylabel('$\\xi$ $[c/\omega_0]$')
    plt.xlabel('$t$ $[\omega_0^{-1}]$')
    plt.xlim([0,xlim_max])
    plt.legend()

    plt.subplot(152)
    plt.plot(t[:l],x2[:l])
    if theory: plt.plot(tt,xx,'--')
    plt.xlabel('$t$ $[\omega_0^{-1}]$')
    plt.ylabel('$x$ $[c/\omega_0]$')
    plt.xlim([0,xlim_max])

    plt.subplot(153)
    plt.plot(t[:l],p1[:l])
    if theory: plt.plot(tt,pzz,'--')
    plt.xlabel('$t$ $[\omega_0^{-1}]$')
    plt.ylabel('$p_z$ $[m_ec]$')
    plt.xlim([0,xlim_max])

    plt.subplot(154)
    plt.plot(t[:l],p2[:l])
    if theory: plt.plot(tt,pxx,'--')
    plt.xlabel('$t$ $[\omega_0^{-1}]$')
    plt.ylabel('$p_x$ $[m_ec]$')
    plt.xlim([0,xlim_max])

    plt.subplot(155)
    plt.plot(t[:l],ene[:l]+1)
    if theory: plt.plot(tt,gg,'--')
    plt.xlabel('$t$ $[\omega_0^{-1}]$')
    plt.ylabel('$\gamma$')
    plt.xlim([0,xlim_max])

    plt.tight_layout()
    if save_fig:
        plt.savefig(dirname+'/'+dirname+'.png',dpi=300)
    plt.show()