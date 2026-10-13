"""Interactive navigation and preset regressions; no files are generated."""
import contextlib
import io
import unittest
from unittest.mock import patch
import ascii_generator as cli


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_back_from_every_chooser(self):
        for chooser in [cli.choose_palette, cli.choose_color_mode, cli.choose_additional,
                        cli.choose_animation, cli.choose_loop, cli.choose_speed,
                        cli.choose_dimensions, cli.choose_character_size, cli.choose_ramp,
                        cli.choose_background, cli.choose_output_format]:
            with self.subTest(chooser=chooser.__name__), patch('builtins.input', return_value='b'):
                self.assertIs(chooser(), cli.BACK)
        with patch('builtins.input', return_value='b'):
            self.assertIs(cli.choose_flag_theme(), cli.BACK_TO_FLAG_THEME)
            self.assertIs(cli.choose_color('Foreground'), cli.BACK)
            self.assertIs(cli.choose_number('Gamma', 1), cli.BACK)

    def test_tetris_chooser_prompt_range_and_navigation(self):
        for answers, default, expected in [(['13'], '1', 'tetris'),
                                            ([''], '1', 'row-reveal'),
                                            ([''], '13', 'tetris'),
                                            (['15', '13'], '1', 'tetris'),
                                            (['14'], '1', 'mosaic'),
                                            (['12'], '1', 'digital-rain'),
                                            ([''], '14', 'mosaic'),
                                            (['b'], '1', cli.BACK)]:
            with self.subTest(answers=answers), patch('builtins.input', side_effect=answers) as read:
                self.assertEqual(cli.choose_animation(default), expected)
                for call in read.call_args_list:
                    self.assertIn(f'1-14, Enter = {default}', call.args[0])
                    self.assertNotIn('1-12', call.args[0])
        with patch('builtins.input', return_value='q'), self.assertRaises(SystemExit) as error:
            cli.choose_animation()
        self.assertEqual(error.exception.code, 0)

    def test_back_revisits_previous_value(self):
        first = iter(['old', 'new']); second = iter([cli.BACK, 'done'])
        values = cli.run_stages([('first', lambda: next(first)), ('second', lambda: next(second))], {}, cli.BACK)
        self.assertEqual(values, dict(first='new', second='done'))

    def test_skip_preserves_existing_value(self):
        values = cli.run_stages([('ramp', lambda: cli.SKIP)], {'ramp': '.@'}, cli.BACK)
        self.assertEqual(values['ramp'], '.@')

    def test_instant_skips_timing_in_both_directions(self):
        animation = iter(['instant', cli.BACK]); dimensions = iter([cli.BACK])
        def forbidden():
            self.fail('Instant asked for timing')
        result = cli.run_stages([('animation', lambda: next(animation)), ('loop', forbidden),
                                 ('speed', forbidden), ('dimensions', lambda: next(dimensions))], {}, cli.BACK)
        self.assertIs(result, cli.BACK)

    def test_additional_and_flag_theme_navigation(self):
        with patch('builtins.input', side_effect=['6', '1', '2']):
            self.assertIs(cli.choose_color_mode(), cli.ADDITIONAL)
            self.assertEqual(cli.choose_additional(), 'flag')
            self.assertEqual(cli.choose_flag_theme()['mode'], 'light')
        with patch('builtins.input', return_value='b'):
            self.assertIs(cli.run_flag('sample.png', {'mode': 'light'}), cli.BACK_TO_FLAG_THEME)

    def test_github_preset_settings(self):
        with patch('builtins.input', return_value=''), patch.object(cli, 'generate') as generate:
            cli.run_preset('sample.png')
        image, values = generate.call_args.args
        self.assertEqual(image, 'sample.png')
        self.assertEqual((values['dimensions'], values['animation'], values['loop'], values['output_format']),
                         ((100, 50), 'twinkle', 'yes', 'svg'))
        self.assertIsNone(values['color']['background'])

    def test_custom_generation_with_new_animation(self):
        with patch('builtins.input', side_effect=['10'] + [''] * 10), patch.object(cli, 'generate') as generate:
            cli.run_normal('sample.png', dict(mode='light', background='#ffffff', foreground='#111111', palette=[]))
        self.assertEqual(generate.call_args.args[1]['animation'], 'typewriter')
        self.assertEqual(generate.call_args.args[1]['dimensions'], (120, 64))

    def test_ambient_and_tetris_timing_reaches_both_export_commands(self):
        for animation in ['twinkle', 'digital-rain', 'tetris', 'mosaic']:
            for speed in ['slow', 'normal', 'fast']:
                for loop in ['yes', 'no']:
                    values = dict(animation=animation, speed=speed, loop=loop,
                                  dimensions=(120, 64), character_size=(8, 15),
                                  ramp=' .:@', contrast=1., brightness=1., gamma=1.,
                                  output_format='gif', color=dict(mode='light',
                                  foreground='#111111', background=None, palette=[]))
                    svg = cli.renderer_command('sample.png', 'out.svg', values)
                    gif = cli.exporter_command('sample.png', 'out.gif', values)
                    self.assertEqual(svg[-3:], [animation, speed, loop])
                    for flag, value in [('--animation', animation), ('--speed', speed), ('--loop', loop)]:
                        self.assertEqual(gif[gif.index(flag) + 1], value)

    def test_ramp_preserves_whitespace_and_command_characters(self):
        for value in ['  .:@', 'back', 'quit', ' .░▒▓█']:
            with patch('builtins.input', return_value=value):
                self.assertEqual(cli.ramp_input('Ramp'), value)
        with patch('builtins.input', return_value=':back'):
            self.assertIs(cli.ramp_input('Ramp'), cli.BACK)

    def test_quit_and_eof_are_clean(self):
        for value in ['q', 'quit']:
            with patch('builtins.input', return_value=value), self.assertRaises(SystemExit) as error:
                cli.command_input('Choice')
            self.assertEqual(error.exception.code, 0)
        with patch('builtins.input', side_effect=EOFError), self.assertRaises(SystemExit) as error:
            cli.command_input('Choice')
        self.assertEqual(error.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
