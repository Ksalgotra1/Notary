import React, { useState, useMemo } from 'react';
import { ImageOff } from 'lucide-react';

function getHashHue(str) {
  if (!str) return Math.floor(Math.random() * 360);
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return Math.abs(hash) % 360;
}

export default function SmartAssetImage({ src, alt, className, style }) {
  const [error, setError] = useState(false);

  // Generate deterministic random hue based on src string so each asset has a unique vibrant hue
  const hue = useMemo(() => getHashHue(src), [src]);
  const hue2 = (hue + 50) % 360;
  const hue3 = (hue + 130) % 360;

  if (error || !src) {
    return (
      <div
        className={`${className || ''} asset-image-fallback`}
        style={{
          width: '100%',
          height: '100%',
          minHeight: '220px',
          background: `linear-gradient(135deg, hsl(${hue}, 60%, 14%) 0%, hsl(${hue2}, 70%, 9%) 50%, hsl(${hue3}, 75%, 5%) 100%)`,
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 'var(--radius)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 12,
          padding: 24,
          position: 'relative',
          overflow: 'hidden',
          ...style,
        }}
      >
        {/* Abstract Random Hue Glow Orbs */}
        <div
          style={{
            position: 'absolute',
            width: '180px',
            height: '180px',
            borderRadius: '50%',
            background: `radial-gradient(circle, hsl(${hue}, 85%, 45%) 0%, transparent 70%)`,
            opacity: 0.4,
            top: '-35px',
            right: '-35px',
            filter: 'blur(32px)',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            width: '200px',
            height: '200px',
            borderRadius: '50%',
            background: `radial-gradient(circle, hsl(${hue2}, 90%, 50%) 0%, transparent 70%)`,
            opacity: 0.3,
            bottom: '-45px',
            left: '-35px',
            filter: 'blur(40px)',
            pointerEvents: 'none',
          }}
        />

        {/* Centered Glassmorphism Error Card */}
        <div
          style={{
            zIndex: 2,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 10,
            background: 'rgba(10, 10, 12, 0.78)',
            backdropFilter: 'blur(12px)',
            padding: '16px 22px',
            borderRadius: '12px',
            border: '1px solid rgba(255, 255, 255, 0.14)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
            maxWidth: '92%',
          }}
        >
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: '50%',
              background: `hsl(${hue}, 70%, 18%)`,
              border: `1px solid hsl(${hue}, 80%, 42%)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ImageOff style={{ width: 20, height: 20, color: `hsl(${hue}, 95%, 75%)` }} />
          </div>
          <span
            style={{
              fontSize: '0.8125rem',
              fontFamily: 'var(--font-heading)',
              color: '#fcfdff',
              fontWeight: 600,
              textAlign: 'center',
              letterSpacing: '-0.01em',
            }}
          >
            Failed to generate image
          </span>
        </div>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt || "Asset thumbnail"}
      className={className}
      style={style}
      onError={() => setError(true)}
    />
  );
}
