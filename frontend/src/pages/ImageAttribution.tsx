// @ts-nocheck
import { useEffect, useState } from 'react';
import { useParams, useLocation } from 'react-router-dom';

import { API } from '../api';
import Seo from '../components/Seo';

// Page showing an image alongside attribution metadata
export default function ImageAttributionPage() {
  const { mid, lang } = useParams();
  const location = useLocation();
  const animalName = location.state?.name;
  const [image, setImage] = useState<any>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setError(false);
    fetch(`${API}/images?mid=${mid}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setImage)
      .catch((err) => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => { controller.abort(); };
  }, [mid]);

  if (error)
    return (
      <div className="page-container">
        <p className="text-danger">Unable to load image.</p>
      </div>
    );
  if (!image)
    return <div className="page-container">Loading...</div>;

  // Prepare responsive image sources
  const sorted = [...(image.variants || [])].sort((a, b) => a.width - b.width);
  const fallback = sorted[0];
  const fallbackSrc = fallback?.thumb_url || image.original_url;
  const unique = [] as any[];
  const seen = new Set();
  for (const v of sorted) {
    if (!seen.has(v.width)) {
      unique.push(v);
      seen.add(v.width);
    }
  }
  const srcSet = unique.map((v) => `${v.thumb_url} ${v.width}w`).join(', ');
  const altText = image.commons_title || animalName || 'Photo on Wikimedia Commons';

  return (
    <div className="page-container">
      <Seo
        title={image.commons_title || 'Image Attribution'}
        description={`Attribution details for ${image.commons_title || 'image'}.`}
        image={image.original_url}
        canonical={`/${lang}/images/${mid}`}
      />
      <img
        src={fallbackSrc}
        srcSet={srcSet}
        sizes="100vw"
        alt={altText}
        className="img-fluid mb-3"
        loading="eager"
        fetchPriority="high"
        decoding="async"
      />
      {/* Metadata list */}
      <dl className="row">
        {image.commons_title && (
          <>
            <dt className="col-sm-3">Title</dt>
            <dd className="col-sm-9">{image.commons_title}</dd>
          </>
        )}
        {image.commons_page_url && (
          <>
            <dt className="col-sm-3">Commons page</dt>
            <dd className="col-sm-9">
              <a href={image.commons_page_url} target="_blank" rel="noopener noreferrer">
                {image.commons_page_url}
              </a>
            </dd>
          </>
        )}
        {image.author && (
          <>
            <dt className="col-sm-3">Author</dt>
            <dd className="col-sm-9">{image.author}</dd>
          </>
        )}
        {image.credit_line && (
          <>
            <dt className="col-sm-3">Credit line</dt>
            <dd className="col-sm-9">{image.credit_line}</dd>
          </>
        )}
        {image.license && (
          <>
            <dt className="col-sm-3">License</dt>
            <dd className="col-sm-9">
              {image.license_url ? (
                <a href={image.license_url} target="_blank" rel="noopener noreferrer">
                  {image.license}
                </a>
              ) : (
                image.license
              )}
            </dd>
          </>
        )}
        {image.attribution_required !== null && (
          <>
            <dt className="col-sm-3">Attribution required</dt>
            <dd className="col-sm-9">{image.attribution_required ? 'Yes' : 'No'}</dd>
          </>
        )}
        {image.original_url && (
          <>
            <dt className="col-sm-3">Download</dt>
            <dd className="col-sm-9">
              <a href={image.original_url} target="_blank" rel="noopener noreferrer">
                Original file
              </a>
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}
