import socket
from time import monotonic, perf_counter
from typing import Annotated, Literal, Optional, Tuple, TypeAlias, Final
from matplotlib import pyplot as plt
import numpy as np
from scipy.fft import fft, fftshift



INT16_FULL_SCALE: Final = 32768.0
COMPLEX_SCALING_FACTOR: Final = 2.0
P_FS: Final = COMPLEX_SCALING_FACTOR * (INT16_FULL_SCALE ** 2)
SOCK_BUF_SZ: Final = 4 * 1024 * 1024


IQInterleavedI16: TypeAlias = Annotated[np.typing.NDArray[np.int16], "int16 LE 1D: i0 q0 i1 q1 ... (interleaved IQ)"]
IQInterleavedF32: TypeAlias = Annotated[np.typing.NDArray[np.float32], "int16 LE 1D: i0 q0 i1 q1 ... (interleaved IQ)"]

INT16_FULL_SCALE = 32768.0
COMPLEX_SCALING_FACTOR = 2.0
P_FS = COMPLEX_SCALING_FACTOR * (INT16_FULL_SCALE ** 2)


def get_scale_from_units(unit: Literal["M", "K"]) -> float:
    if unit == "K": return 1e-3
    if unit == "M": return 1e-6
    return 1


class VSA:
    def __init__(
        self,
        freqs: np.ndarray,
        use_dbfs: bool,
        freq_units: Literal["M", "K"] = "M",
        spec_y_lim: Optional[Tuple[float, float]] = None,
        spec_y_hyst_up: float = 3.0,
        spec_y_hyst_dn: float = 3.0,
        render_dt: float = 0.1,
        title_base: Optional[str] = None
    ):
        """
        Spectrum visualization only.
        """
        self.freq_units = freq_units
        self.freq_scale: float = get_scale_from_units(freq_units)

        self.freqs = freqs
        self.x_freq = self.freqs * self.freq_scale

        self.dF = float(self.freqs[1] - self.freqs[0])
        self._y_label_spec = "power (dBFS)" if use_dbfs else "magn (linear)"
        self.use_dbfs = use_dbfs
        
        self._base_title = title_base if title_base else (
            f"SPECTRUM  FFT={len(freqs)}  |  dF={self.dF * self.freq_scale:.3f} {freq_units}Hz"
        )

        # Hard y-limits
        self._spec_y_lim: Optional[Tuple[float, float]] = spec_y_lim

        # Hysteresis for spectrum (independent)
        self._spec_y_hyst_up = float(spec_y_hyst_up)
        self._spec_y_hyst_dn = float(spec_y_hyst_dn)

        # Guard fraction for y-limit updates
        self._y_guard_frac = 0.10

        # Render pacing
        self.render_dt = float(render_dt)

        # Spectrum y-scale state
        self._spec_ylim_inited = False
        self._spec_ymin = 0.0
        self._spec_ymax = 0.0

        # Control
        self._stop = False
        self.paused: bool = False
        self._step_delta: int = 0

        # Figure + subplot
        self.fig, self.ax_spec = plt.subplots(figsize=(12, 6))
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        self.fig.canvas.mpl_connect("close_event", self._on_figure_close)

        # ===== SPECTRUM PANEL =====
        bar_w = (self.dF * self.freq_scale) * 0.95
        self._bars_raw = self.ax_spec.bar(
            self.x_freq,
            np.zeros_like(self.x_freq),
            width=bar_w,
            bottom=0.0,
            align="center",
            color="orange",
            linewidth=0.0,
            zorder=1,
        )

        (self._line_smooth_spec,) = self.ax_spec.plot(
            self.x_freq,
            np.zeros_like(self.x_freq),
            color="black",
            zorder=3,
        )
        self._line_smooth_spec.set_visible(False)

        self.ax_spec.set_xlabel(f"frequency ({freq_units}Hz)")
        self.ax_spec.set_ylabel(self._y_label_spec)
        self.ax_spec.set_title(self._base_title)
        self.ax_spec.grid(True)

        if self._spec_y_lim is not None:
            self.ax_spec.set_ylim(self._spec_y_lim[0], self._spec_y_lim[1])

        self.fig.tight_layout(pad=2)
        self.fig.canvas.draw_idle()
        plt.pause(self.render_dt)

    def _on_figure_close(self, ev) -> None:
        """Handle window close by user (X button)"""
        print(f"[_ON_FIGURE_CLOSE] Figure closed by user", flush=True)
        self._stop = True

    def _on_key(self, ev) -> None:
        print(f"[_ON_KEY] key={ev.key!r}", flush=True)
        if ev.key == "escape":
            self._stop = True
            print(f"[_ON_KEY] closing figure via ESC", flush=True)
            plt.close(self.fig)
        elif ev.key in (" ", "space"):
            self.paused = not self.paused
            print(f"[_ON_KEY] paused toggled to {self.paused}", flush=True)
        elif ev.key == "right":
            if self.paused:
                self._step_delta += 1
                print(f"[_ON_KEY] step_delta incremented to {self._step_delta}", flush=True)
        elif ev.key == "left":
            if self.paused:
                self._step_delta -= 1
                print(f"[_ON_KEY] step_delta decremented to {self._step_delta}", flush=True)

    def get_and_clear_step_delta(self) -> int:
        """Returns accumulated step delta and clears it."""
        delta = self._step_delta
        self._step_delta = 0
        return delta

    @property
    def stop_requested(self) -> bool:
        return self._stop

    def figure_alive(self) -> bool:
        """Check if figure window still exists"""
        try:
            return plt.fignum_exists(self.fig.number)
        except Exception:
            return False

    def _update_spec_ylim(self, y_ref: np.ndarray) -> float:
        """
        Update spectrum y-limits with hysteresis.
        Returns y_bottom for bar positioning.
        """
        if self._spec_y_lim is not None:
            return float(self._spec_y_lim[0])

        y_min = float(np.min(y_ref))
        y_max = float(np.max(y_ref))

        if not self._spec_ylim_inited:
            span = max(y_max - y_min, 1e-12)
            guard = self._y_guard_frac * span
            self._spec_ymin = y_min - guard
            self._spec_ymax = y_max + guard
            self._spec_ylim_inited = True
        else:
            span = max(self._spec_ymax - self._spec_ymin, y_max - y_min, 1e-12)
            guard = self._y_guard_frac * span

            if y_max > self._spec_ymax + self._spec_y_hyst_up:
                self._spec_ymax = y_max + guard
            if y_min < self._spec_ymin - self._spec_y_hyst_dn:
                self._spec_ymin = y_min - guard

        self.ax_spec.set_ylim(self._spec_ymin, self._spec_ymax)
        return self._spec_ymin

    def update(
        self,
        spectr_arr: np.ndarray,
        smoothed: Optional[np.ndarray] = None,
        title: Optional[str] = None,
    ) -> None:
        """
        Update spectrum panel.

        Contract:
        - spectr_arr: 1D array, len == len(freqs)
        - smoothed: optional 1D array, same length as spectr_arr
        - title: optional suffix for main title
        """
        # ===== SPECTRUM PANEL =====
        if smoothed is None:
            self._line_smooth_spec.set_visible(False)
            y_ref = spectr_arr
        else:
            self._line_smooth_spec.set_ydata(smoothed)
            self._line_smooth_spec.set_visible(True)
            y_ref = smoothed

        _title = self._base_title
        if title:
            _title += f"\n{title}"
        self.ax_spec.set_title(_title)

        spec_y_bottom = self._update_spec_ylim(y_ref)

        for rect, yv in zip(self._bars_raw, spectr_arr):
            rect.set_y(spec_y_bottom)
            rect.set_height(float(yv) - spec_y_bottom)

        self.fig.canvas.draw_idle()
        plt.pause(self.render_dt)

class RingBuffer:
    """
    Циклічний буфер для накопичення int16 даних без переалокацій.
    Архітектура:
    - Основний буфер: int16 дані (циклічний write_pos/read_pos)
    """
    
    def __init__(self, el_count: int):
        self.buffer = np.empty(el_count, dtype=np.int16)
        self.el_count = el_count
        self.write_pos = 0
        self.read_pos = 0
        self.el_available = 0

    def push_raw_data(self, data: IQInterleavedI16, seq_n: Optional[int]=None) -> int:
        """
        Додаємо IQInterleavedI16 дані
        Args:
            data: IQInterleavedI16 (memoryview або np.ndarray з int16)
            seq_n: seq_num пакету (опціонально)
        Returns:
            кількість доданих елементів (int16)
        """
        count: int = len(data)
        
        # Записуємо дані в основний буфер
        if self.write_pos + count <= self.el_count:
            self.buffer[self.write_pos:self.write_pos + count] = data[:count]
        else:
            first_chunk = self.el_count - self.write_pos
            self.buffer[self.write_pos:] = data[:first_chunk]
            self.buffer[:count - first_chunk] = data[first_chunk:count]
        
        # Обюробляємо seq_num (додам пізніше)
        if seq_n is not None:
            ...
        self.write_pos = (self.write_pos + count) % self.el_count
        self.el_available = min(self.el_available + count, self.el_count)
        return count
    
    def pop_raw_data(self, count: int) -> Optional[IQInterleavedI16]:
        """
        Повертає count int16 елементів (або всі наявні).
        """
        if self.el_available == 0:
            return None
        count = min(count, self.el_available)
        out = np.empty(count, dtype=np.int16)
        
        # Читаємо дані з циклічного буфера
        if self.read_pos + count <= self.el_count:
            out[:] = self.buffer[self.read_pos:self.read_pos + count]
        else:
            first_chunk = self.el_count - self.read_pos
            out[:first_chunk] = self.buffer[self.read_pos:]
            out[first_chunk:] = self.buffer[:count - first_chunk]
        self.read_pos = (self.read_pos + count) % self.el_count
        self.el_available -= count
        return out

    def read_samples(self, samp_count: int) -> Optional[IQInterleavedI16]:
        """
        Domain semantic. Wrapper over pop_raw_data
        Читаємо samp_count IQ пар.
        sample is 2x raw
        """
        raw_count = samp_count * 2
        return self.pop_raw_data(raw_count)
    
    def available(self) -> int:
        """Скільки raw int16 елементів доступно"""
        return self.el_available

# =====================================================
# UDP Payload обробка
# =====================================================
def _proc_udp_payload(data: bytes, hdr_sz: int) -> Tuple[memoryview, memoryview, str]:
    """
    Обробка UDP payload: пропуск заголовка.
    Повертає в'ю (zero-copy), не копію.
    
    Args:
        data: bytes дані пакету
        hdr_sz: розмір заголовка
        
    Returns:
        (memoryview без заголовка, рядок для діагностики)
    """
    ts = "no header"
    if hdr_sz:
        ts = f"header {hdr_sz} B"
    return memoryview(data)[hdr_sz:], memoryview(data)[:hdr_sz], ts


# =====================================================
# FFT batch core
# =====================================================
from scipy.fft import fft, fftshift
def batch_fft(
    batch_inp: np.ndarray,      # (fft_batch * fft_n,), complex64/128, C-contiguous
    fft_n: int,                 # FFT window size
    fft_batch: int,             # number of windows in batch
    power_db: np.ndarray,       # (fft_n,), float32, preallocated
    p_fs: float = P_FS,                # full-scale power reference
    *,
    workers: int = -1,
) -> None:
    """

    Computes averaged power spectrum over fft_batch windows.

    Semantics (C-equivalent):
      - fft_batch independent FFTs of length fft_n
      - |X|^2 computed per window
      - averaged over windows
      - scaled and converted to dBFS
      - FFT-shifted

    Output is written in-place to power_db.
    """

    # --- batch FFT ---
    X = fft(
        batch_inp.reshape(fft_batch, fft_n),
        axis=1,
        workers=workers,
    )

    # --- power accumulation + averaging ---
    mag2 = (X.real * X.real + X.imag * X.imag).mean(axis=0)
    mag2 /= (fft_n * fft_n)

    # --- dBFS ---
    power_db[:] = 10.0 * np.log10(
        np.maximum(mag2 / p_fs, 1e-30)
    ).astype(np.float32)

    # --- frequency centering ---
    power_db[:] = fftshift(power_db)


def do_work(
    port: int,
    rd_timeout_ms: int = 750,
    hdr_sz: int = 8,
    pack_sz: int = 8192 + 8,
    Fs: float = 480e3,
    Fc: float = 0,
    fft_n: int = 1024,
    sigma: float = 1.75,
    ema_alpha: Optional[float] = 0.1,
) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", port))
    s.settimeout(rd_timeout_ms / 1000.0)

    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCK_BUF_SZ)
    print(f"[do_vsa_socket] listening on port {port}", flush=True)
    print(f"[do_vsa_socket] {pack_sz=:_}, {hdr_sz=}", flush=True)
    
    # ===== RING BUFFER =====
    
    ring_buffer_size = fft_n * 1_000
    ring_buf = RingBuffer(ring_buffer_size)
    fft_batch : int = 8 # fft windows in batch
    batch_len = fft_n * fft_batch
    need_raw = batch_len * 2  # бо в рінгу interleaved i16: i0 q0 i1 q1 ...
    # ===== PRE-ALLOC BUFFERS FOR FFT =====
    batch_inp = np.empty(batch_len, dtype=np.complex64)
    power_db: IQInterleavedF32 = np.empty(fft_n, dtype=np.float32) # for acumulate batch result as sum I*I + Q*Q over all windows and averaged, normalazide to dbfs
    # ===== FREQUENCY BINS =====
    dF = Fs / fft_n
    freq_bins = (np.arange(fft_n, dtype=np.float32) - (fft_n // 2)) * dF + Fc
    pkt_buf = np.empty(pack_sz, dtype=np.uint8)
    
    if 0:
        vsa = VSA(
            freq_bins,
            render_dt=0.0001,
            spec_y_lim=None,
            use_dbfs=True
        )
    else:
        vsa = None
    
    pkt_count = 0
    batches_processed = 0
    seq_num: np.int64 = None
    gap_count = 0
    gap_len = 0
    t_start = t0 = monotonic()
    pkt_count_0 = pkt_count
    byte_count_0 = 0
    fft_calls = fft_time_acc = 0
    while True:
        if vsa and vsa.stop_requested:
            print(f"[DBG] fig close requested")
            break
        try:
            n = s.recv_into(pkt_buf, pack_sz)
            byte_count_0 += n
        except socket.timeout:
            continue
        pkt_count += 1
        payload, hdr, _ = _proc_udp_payload(pkt_buf, hdr_sz)
        curr_num = np.frombuffer(hdr, np.int64)
        if seq_num is not None:
            gap = curr_num - seq_num
            if gap > 1:
                gap_count += 1
                gap_len += gap
                print(f"[DBG] {gap=} ({gap_count=}  {pkt_count:_})")
        seq_num = curr_num
        ring_buf.push_raw_data(payload, seq_num)

        if ring_buf.available() != need_raw:
            continue

        raw_iq_i16 = ring_buf.pop_raw_data(need_raw)
        if raw_iq_i16 is None:
            continue

        i = raw_iq_i16[0::2].astype(np.float32, copy=False)
        q = raw_iq_i16[1::2].astype(np.float32, copy=False)
        batch_inp.real = i
        batch_inp.imag = q

        t_fft0 = perf_counter()
        batch_fft(batch_inp, fft_n, fft_batch, power_db)
        t_fft1 = perf_counter()

        fft_time_acc += (t_fft1 - t_fft0)
        fft_calls += 1

        
        batches_processed += 1
        stt_str = f"{pkt_count:6_}  {batches_processed:6_}  {gap_count=:_}"
        if vsa: vsa.update(power_db, None, stt_str)
        if batches_processed % 1000 == 0:
            t1 = monotonic()
            uptime = t1 - t_start
            dt = t1 - t0
            if dt > 0:
                pkt_rate = (pkt_count - pkt_count_0) / dt          # pkt/s

                Bps = byte_count_0 / dt                          # bytes per second
                mib_rate = Bps / (1024 * 1024)                   # MiB/s
                mbps_rate = (Bps * 8) / 1_000_000                # Mbps (SI)
                avg_fft_ms = (fft_time_acc / max(fft_calls, 1)) * 1e3
                
                print(
                    f"[RATE]  "
                    f"{pkt_rate:8.1f} pkt/s   "
                    f"{mib_rate:6.2f} MiB/s   "
                    f"{mbps_rate:6.2f} Mbps"
                    f"dt={dt:6.2f}s   "
                    f"fft={avg_fft_ms:6.3f} ms"
                    f"up={uptime:8.1f}s"
                )

            # reset window
            t0 = t1
            pkt_count_0 = pkt_count
            byte_count_0 = 0

if __name__ == '__main__':
    try:
        do_work(9999)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[ERR] exception: {e}")
        
