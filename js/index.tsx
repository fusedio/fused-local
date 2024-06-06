import { createRoot } from 'react-dom/client';
import HelloWorld from './hello.tsx';

const App = () => {
    return (
        <body>
            <main>
                <section>
                    <HelloWorld />
                </section>
            </main>
        </body>
    );
}

createRoot(document.getElementById('app') as HTMLElement).render(<App />);
