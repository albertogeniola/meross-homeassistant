import { Pipe, PipeTransform } from '@angular/core';
import { parse, ParsedSpan } from 'ansicolor';

@Pipe({
  name: 'ansiparser',
})
export class AnsiparserPipe implements PipeTransform {
  transform(value: string): ParsedSpan[] {
    return parse(value).spans;
  }
}
