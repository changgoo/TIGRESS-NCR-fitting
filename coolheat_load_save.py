import os
import xarray as xr
import numpy as np
import shutil
import gc

from pyathena.tigress_ncr.zprof import zprof_rename
from pyathena.tigress_ncr.ncr_paper_lowz import LowZData


def load_hst(pdata, m):
    s = pdata.sa.set_model(m)
    Lz = s.domain["Lx"][2]
    vol = np.prod(s.domain['Lx'])
    area = s.domain["Lx"][0] * s.domain["Lx"][1]

    h = pdata.set_global_history(m, recal=False)

    band = ["LyC", "LW", "PE"]
    flist = [
        "time",
        "tMyr",
        "Srad",
        "Sheat",
        "Scool",
        "Snet",
        "SSN",
        "SKE",
        "sfr10",
        "sfr40",
        "sfr100",
    ]
    for f in range(3):
        for head in ["Sabs_", "Sabs_gas_", "Sabs_dust_", "S"]:
            fname = f"{head}{band[f]}"
            if fname in h:
                flist.append(fname)

    # setting time array in code units
    trange = pdata.get_trange(s)
    tstr = max(trange.start / s.u.Myr, h["time"].min())
    tend = min(trange.stop / s.u.Myr, h["time"].max())
    dt = s.par["output5"]["dt"]*0.5
    tarr = np.arange(tstr, tend, dt)
    tarr_c = 0.5 * (tarr[1:] + tarr[:-1])

    # store data from history
    hdict = dict()
    for f in flist:
        hdict[f] = np.interp(tarr_c, h["time"], h[f])

    # store data from cumulative history
    hw = s.read_hst_phase(iph=0)
    hst_cum = dict()
    hst_cum["Fout"] = hw["Fze_upper_dt"] - hw["Fze_lower_dt"]
    hst_cum["Rxy"] = hw["Rxy_L_dt"] * Lz
    hst_cum["Mxy"] = hw["Mxy_L_dt"] * Lz
    hst_cum["Gext"] = hw["Ephi_ext_dt"] * Lz
    hst_cum["Gsg"] = hw["Ephi_sg_dt"] * Lz
    hst_cum["Gtid"] = hw["Ephi_tidal_dt"] * Lz
    hst_cum["Esink"] = hw["sink_E_dt"] * Lz
    hst_cum["cool"] = hw["coolrate_dt"] * Lz
    hst_cum["heat"] = hw["heatrate_dt"] * Lz
    hst_cum["net"] = hw["netcool_dt"] * Lz

    for k in hst_cum:
        hcum = hst_cum[k]#.cumsum(dim="time")
        hcum_i = np.interp(tarr, hw["time"], hcum)
        hdict[k] = np.diff(hcum_i) / dt * s.u.Lsun

    # save data into dataset
    dset = xr.Dataset()
    for k in hdict:
        dset[k] = xr.DataArray(hdict[k], coords=[tarr_c], dims=["time_code"])

    return dset


def load_save_hst():
    tmp_outdir = "./lowZ-hst-data"
    os.makedirs(tmp_outdir, exist_ok=True)
    pdata = LowZData()

    for m in pdata.mlist:
        print(m)
        hdset = load_hst(pdata, m)
        hdset.to_netcdf(os.path.join(tmp_outdir, f"{m}_hst.nc"))


def load_save_zprof():
    tmp_outdir = "./lowZ-zprof-data"
    os.makedirs(tmp_outdir, exist_ok=True)

    flist = ["A", "d", "Ek1", "Ek2", "Ek3", "dEk2", "cool", "heat", "net_cool", "P"]
    pdata = LowZData()
    for m in pdata.mlist:
        print(m)
        s = pdata.sa.set_model(m)
        f = os.path.join(tmp_outdir, f"{s.basename}_newzp.nc")

        s.zp = s.read_zprof_new(flist=flist)
        trange = pdata.get_trange(s)
        area = s.domain["Lx"][0] * s.domain["Lx"][1]
        s.newzp = zprof_rename(s).sel(time=trange) * area
        s.newzp.to_netcdf(f)
        delattr(s, "zp")
        gc.collect()


def copy_files(m):
    basedir = "/scratch/gpfs/changgoo/TIGRESS-NCR"
    savdir = os.path.join(basedir, m)

    indir = os.path.join(savdir, "hst2")
    outdir = "./lowZ-coolheat-data"
    os.makedirs(outdir, exist_ok=True)
    for f in ["PEheating.nc", "phase_vmeans.nc", "phase_nmeans.nc"]:
        infile = os.path.join(indir, f)
        outfile = os.path.join(outdir, f"{m}_{f}")
        shutil.copy2(infile, outfile)
    return


if __name__ == "__main__":
    # "qdset" is a xarray.Dataset storing the (16, 50, 84) percentile values and mean and std for each model's time series into an effectively 3D array.

    # with xr.open_dataarray("percentiles_all.nc") as qdset:
    #     # get median values and convert it into pandas.DataFrame
    #     mid_df = qdset.sel(q="50").to_dataset(dim="variable").drop("q").to_dataframe()
    #     mid_logdf = np.log10(mid_df)

    # for m in qdset["name"].data:
    #     # da,vavg,navg = retrieve_timeseries(m)
    #     copy_files(m)

    # load_save_zprof()

    load_save_hst()
