import { AnsiparserPipe } from './ansiparser.pipe';

describe('AnsiparserPipe', () => {
  it('create an instance', () => {
    const pipe = new AnsiparserPipe();
    expect(pipe).toBeTruthy();
  });
});
