import BundleGrid from './BundleGrid';
import css from './BundlesBrowseScreen.module.css';

export default function BundlesBrowseScreen() {
  return (
    <div className={css.screen}>
      <a href="/" className={css.backLink}>
        ← Back to Home
      </a>
      <BundleGrid />
    </div>
  );
}
