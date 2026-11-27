import { useState } from 'react';
import { Box, Button, Collapse, Divider, Slider, Stack, Switch, Typography } from '@mui/material';
import { MUTED } from '../../constants';
import {
  DELAY_MS_MAX,
  LOSS_PERCENT_MAX,
  type NetConfig,
  type NetStats,
} from '../../types/network';

interface NetworkPanelProps {
  config: NetConfig;
  stats: NetStats;
  // False until the server sends stats. Settings still change locally and are
  // sent once it does.
  supported: boolean;
  onConfigChange: (changes: Partial<NetConfig>) => void;
  onResetStats: () => void;
}

const btnSx = {
  fontSize: 13,
  fontWeight: 500,
  textTransform: 'none',
  color: '#b4b4b4',
  borderColor: '#404040',
  borderRadius: '8px',
  px: '16px',
  height: 34,
} as const;

const labelSx = { fontSize: 13, color: '#b4b4b4' } as const;
const valueSx = { fontSize: 13, color: '#ececec', fontVariantNumeric: 'tabular-nums' } as const;

const sliderSx = {
  color: '#3f8a57',
  py: '10px',
  '& .MuiSlider-thumb': { width: 14, height: 14 },
} as const;

function percentSaved(raw: number, sent: number): string {
  if (raw === 0) return '—';
  return `${(((raw - sent) / raw) * 100).toFixed(1)}%`;
}

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
      <Typography sx={{ fontSize: 13, color: MUTED }}>{label}</Typography>
      <Typography sx={valueSx}>{typeof value === 'number' ? value.toLocaleString() : value}</Typography>
    </Box>
  );
}

interface SettingSliderProps {
  label: string;
  unit: string;
  value: number;
  max: number;
  step: number;
  onCommit: (value: number) => void;
}

// Shows the value while dragging and sends it only on release.
function SettingSlider({ label, unit, value, max, step, onCommit }: SettingSliderProps) {
  const [dragValue, setDragValue] = useState<number | null>(null);
  const shown = dragValue ?? value;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <Typography sx={labelSx}>{label}</Typography>
        <Typography sx={valueSx}>
          {shown}
          {unit}
        </Typography>
      </Box>
      <Slider
        size="small"
        aria-label={label}
        min={0}
        max={max}
        step={step}
        value={shown}
        onChange={(_, next) => setDragValue(next as number)}
        onChangeCommitted={(_, next) => {
          setDragValue(null);
          onCommit(next as number);
        }}
        sx={sliderSx}
      />
    </Box>
  );
}

function SettingSwitch({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <Typography sx={labelSx}>{label}</Typography>
      <Switch
        size="small"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        slotProps={{ input: { 'aria-label': label } }}
        sx={{
          '& .MuiSwitch-switchBase.Mui-checked': { color: '#46955f' },
          '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { backgroundColor: '#3f8a57' },
        }}
      />
    </Box>
  );
}

export default function NetworkPanel({ config, stats, supported, onConfigChange, onResetStats }: NetworkPanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <Box sx={{ pt: '20px' }}>
      <Button
        variant="outlined"
        onClick={() => setOpen((previous) => !previous)}
        aria-expanded={open}
        aria-controls="network-panel"
        sx={btnSx}
      >
        {open ? 'Hide network stats' : 'Network stats'}
      </Button>

      <Collapse in={open} unmountOnExit>
        <Stack id="network-panel" spacing="14px" sx={{ pt: '16px' }}>
          {!supported && (
            <Typography sx={{ fontSize: 12, color: MUTED }}>
              Waiting for the server to report stats. Settings will be sent when it does.
            </Typography>
          )}

          <Stack spacing="4px">
            <SettingSlider
              label="Packet loss"
              unit="%"
              value={config.lossPercent}
              max={LOSS_PERCENT_MAX}
              step={1}
              onCommit={(lossPercent) => onConfigChange({ lossPercent })}
            />
            <SettingSlider
              label="Delay"
              unit=" ms"
              value={config.delayMs}
              max={DELAY_MS_MAX}
              step={10}
              onCommit={(delayMs) => onConfigChange({ delayMs })}
            />
            <SettingSwitch
              label="Delta compression"
              checked={config.deltaCompression}
              onChange={(deltaCompression) => onConfigChange({ deltaCompression })}
            />
            <SettingSwitch
              label="Huffman coding"
              checked={config.huffmanCoding}
              onChange={(huffmanCoding) => onConfigChange({ huffmanCoding })}
            />
          </Stack>

          <Divider sx={{ borderColor: 'rgba(236,236,236,.14)' }} />

          <Stack spacing="6px">
            <StatRow label="Packets sent" value={stats.packetsSent} />
            <StatRow label="Packets received" value={stats.packetsReceived} />
            <StatRow label="Packets dropped" value={stats.packetsDropped} />
            <StatRow label="Stale packets discarded" value={stats.stalePackets} />
          </Stack>

          <Stack spacing="6px">
            <StatRow label="Bytes raw" value={stats.bytesRaw} />
            <StatRow label="Bytes sent" value={stats.bytesSent} />
            <StatRow label="Saved" value={percentSaved(stats.bytesRaw, stats.bytesSent)} />
            {stats.avgLatencyMs !== null && (
              <StatRow label="Avg latency" value={`${stats.avgLatencyMs.toFixed(0)} ms`} />
            )}
          </Stack>

          <Button variant="outlined" onClick={onResetStats} sx={{ ...btnSx, alignSelf: 'flex-start' }}>
            Reset stats
          </Button>
        </Stack>
      </Collapse>
    </Box>
  );
}
